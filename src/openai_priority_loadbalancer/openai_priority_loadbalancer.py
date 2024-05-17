"""Module providing a prioritized load-balancing for Azure OpenAI."""

import logging
import random
import traceback
from typing import List
from datetime import datetime, MAXYEAR, MINYEAR, timedelta, timezone
import httpx    # import the entirety of the httpx module to avoid potential conflicts with AsyncClient in the openai package by using httpx. notation

class Backend:
    """Class representing a backend object used with Azure OpenAI, etc."""

    # Constructor
    def __init__(self, host: str, priority: int):
        # Public instance variables
        self.host = host
        self.is_throttling = False
        self.priority = priority
        self.retry_after = datetime.min
        self.successful_call_count = 0

# Reference design at https://github.com/encode/httpx/blob/master/httpx/_transports/base.py
# BaseLoadBalancer providing functionality to both synchronous and asynchronous load balancers
class BaseLoadBalancer():
    """Logically abstracts the BaseLoadBalancer class which should be inherited by the synchronous and asynchronous load balancer classes."""

    # Constructor
    def __init__(self, transport, backends: List[Backend]):
        # Public instance variables
        self.backends = backends

        # "Private" instance variables
        self._backend_index = -1
        self._log = logging.getLogger("openai-priority-loadbalancer")     # https://www.loggly.com/ultimate-guide/python-logging-basics/
        self._available_backends = 1
        self._transport = transport

    # "Protected" Methods
    def _check_throttling(self):
        """Check if any backend is throttling and reset if necessary."""

        min_datetime = datetime(MINYEAR, 1, 1, tzinfo = timezone.utc)

        for backend in self.backends:
            if backend.is_throttling and datetime.now(timezone.utc) >= backend.retry_after:
                backend.is_throttling = False
                backend.retry_after = min_datetime
                self._log.info("Backend %s is no longer throttling.", backend.host)

    def _get_backend_index(self):
        """Return a backend list index of a highest-priority available backend to be used. If no backend is available, -1 will be returned."""

        selected_priority = float('inf')
        available_backends = []

        # 1) Evaluate all defined backends for availability and priority, leaving only the highest-priority available backends from which to select an index.
        for i, backend in enumerate(self.backends):
            if not backend.is_throttling:
                backend_priority = backend.priority

                # If a backend has a (logically) higher priority (1 would be logically higher than 2, etc.), we select that priority, clear the available backends list
                # which contains lower-priority backends, then add the higher-priority backend(s) to the list.
                if backend_priority < selected_priority:
                    selected_priority = backend_priority
                    available_backends.clear()
                    available_backends.append(i)
                elif backend_priority == selected_priority:
                    available_backends.append(i)

        # 2) Select an available backend index. If there is only one available backend, it will be selected. If there are multiple available backends, one will be randomly selected. If there are none, we return -1.
        if len(available_backends) == 1:
            return available_backends[0]

        if len(available_backends) > 0:
            # Since this code is very likely being called from multiple python instances with multiple workers in parallel executions, there's no way to distribute requests
            # uniformly across all Azure OpenAI instances.
            # Doing so would require a centralized service, cache, etc. to keep track of a common backends list, but that would also imply a locking mechanism for updates, which would
            # immediately inhibit the performance benefits of the load balancer. This is why this is more of a pseudo load-balancer. Therefore, we'll just randomize across the available backends.
            return random.choice(available_backends)

        # If there are no available backends, -1 will be returned to indicate that nothing is available (and that we consequently need to bail by returning an HTTP 429).
        return -1

    def _get_available_backends(self):
        """Return the backends that are not actively throttled. This subset is the set of available backends."""

        self._available_backends = 0

        for backend in self.backends:
            if not backend.is_throttling:
                self._available_backends += 1

        self._log.info("Available backends: %s/%s", self._available_backends, len(self.backends))

        return self._available_backends

    def _get_soonest_retry_after(self):
        """Return the soonest retry-after time in seconds among all throttling backends. This provides for the quickest retry time to be returned with the HTTP 429."""

        soonest_retry_after = datetime(MAXYEAR, 1, 1, tzinfo = timezone.utc)

        for backend in self.backends:
            if backend.is_throttling and backend.retry_after < soonest_retry_after:
                soonest_retry_after = backend.retry_after
                soonest_backend = backend.host

        # As the `int` cast truncates the decimal, we need to add 1 to the result to ensure that the delay is at least the number of seconds needed.
        delay = int((soonest_retry_after - datetime.now(timezone.utc)).total_seconds()) + 1
        self._log.info("The soonest retry to an available backend would be to %s after %s %s.", soonest_backend, delay, "second" if delay == 1 else "seconds")

        return delay

    def _handle_200_399_response(self, request, response, backend_index):
        """Handle a successful response from the backend."""

        self._log.info("Request sent to server: %s, Status code: %s", request.url, response.status_code)
        self.backends[backend_index].successful_call_count += 1

        return response

    def _handle_429_5xx_response(self, request, response, backend_index):
        """Handle a 429 or 5xx response from the backend by identifying the retry-after interval, if available, and updating the available backends."""

        self._log.info("Request sent to server: %s, Status code: %s - FAIL", request.url, response.status_code)

        # 1) Determine the retry-after interval, if possible; otherwise, assign -1 to indicate that no delay is needed.
        retry_after = int(response.headers.get('Retry-After', '-1'))

        if retry_after == -1:
            retry_after = int(response.headers.get('x-ratelimit-reset-requests', '-1'))

        if retry_after == -1:
            retry_after = int(response.headers.get('x-ratelimit-reset-requests', '10'))

        self._log.info("Backend %s is throttling. Retry after %s %s.", self.backends[backend_index].host, retry_after, "second" if retry_after == 1 else "seconds")

        # 2) Regardless of whether the response indicates a 429 or 5xx error, we mark the backend as throttling to temporarily take it out of the available backend pool.
        backend = self.backends[backend_index]
        backend.is_throttling = True
        backend.retry_after = datetime.now(timezone.utc) + timedelta(seconds = retry_after)

        # 3) Update the available backends.
        self._get_available_backends()

    def _handle_4xx_response(self, request, response):
        """Handle a 4xx response other than 429 from the backend."""

        self._log.warning("Request sent to server: %s, Status code: %s - FAIL", request.url, response.status_code)

        return response

    def _modify_request(self, request, backend_index):
        """Modifies the URL and Host header with the desired backend target. This ensures that the request is sent to the chosen backend server."""

        # Modify the request. Note that only the URL and Host header are being modified on the original request object. We make the smallest incision possible to avoid side effects.
        # Update URL and host header as both must match the backend server.
        request.url = request.url.copy_with(host = self.backends[backend_index].host)
        request.headers = request.headers.copy()    # We need to create a mutable copy of the headers before we modify and assign them back to the request object.
        request.headers['host'] = self.backends[backend_index].host

    def _return_429(self):
        """Return an HTTP 429 response with a Retry-After header value. This is returned to the caller of this load balancer when no backends are available."""

        self._log.warning("No backend available!")
        retry_after = str(self._get_soonest_retry_after())
        self._log.info("Returning HTTP 429 with Retry-After header value of %s %s.", retry_after, "second" if retry_after == "1" else "seconds")

        return httpx.Response(429, content = '', headers={'Retry-After': retry_after})

class AsyncLoadBalancer(BaseLoadBalancer):
    """Asynchronous Load Balancer class based on BaseLoadBalancer"""

    # Constructor
    def __init__(self, backends: List[Backend]):
        super().__init__(httpx.AsyncClient(), backends)

    # Public Methods
    async def handle_async_request(self, request):
        """Handles an asynchronous request by issuing an asynchronous request to an available backed."""

        self._log.info("Intercepted and now handling an asynchronous request.")

        # Identify whether any backend is throttling and reset if necessary, then update the remaning available backends prior to any request handling.
        self._check_throttling()
        self._get_available_backends()
        response = None

        while self._available_backends > 0:
            # 1) Determine the appropriate backend to use
            backend_index = self._get_backend_index()

            if backend_index == -1:
                return self._return_429()

            # 2) Modify the intercepted request
            self._modify_request(request, backend_index)

            # 3) Send the request to the selected backend (via async)
            try:
                response = await self._transport.send(request)
            except Exception:
                self._log.error(traceback.print_exc())

            # 4) Evaluate the response from the backend:
            #    If 429 or a 5xx error, we continue the loop and retry with another backend, if available.
            #    If 200-399, we return the successful response.
            #    If any other 4xx error, we break the loop and return the response as we don't explicitly handle these client errors.
            if response is not None and (response.status_code == 429 or response.status_code >= 500):
                self._handle_429_5xx_response(request, response, backend_index)
                continue

            if response is not None and (response.status_code >= 200 and response.status_code <= 399):
                return self._handle_200_399_response(request, response, backend_index)

            return self._handle_4xx_response(request, response)

        # Since no backends are available, we must return a 429.
        return self._return_429()

class LoadBalancer(BaseLoadBalancer):
    """Synchronous Load Balancer class based on BaseLoadBalancer"""

    # Constructor
    def __init__(self, backends: List[Backend]):
        super().__init__(httpx.Client(), backends)

    # Public Methods
    def handle_request(self, request):
        """Handles a synchronous request by issuing a request to an available backed."""

        self._log.info("Intercepted and now handling a synchronous request.")

        # Identify whether any backend is throttling and reset if necessary, then update the remaning available backends prior to any request handling.
        self._check_throttling()
        self._get_available_backends()
        response = None

        while self._available_backends > 0:
            # 1) Determine the appropriate backend to use
            backend_index = self._get_backend_index()

            if backend_index == -1:
                return self._return_429()

            # 2) Modify the intercepted request
            self._modify_request(request, backend_index)

            # 3) Send the request to the selected backend
            try:
                response = self._transport.send(request)
            except Exception:
                self._log.error(traceback.print_exc())

            # 4) Evaluate the response from the backend:
            #    If 429 or a 5xx error, we continue the loop and retry with another backend, if available.
            #    If 200-399, we return the successful response.
            #    If any other 4xx error, we break the loop and return the response as we don't explicitly handle these client errors.
            if response is not None and (response.status_code == 429 or response.status_code >= 500):
                self._handle_429_5xx_response(request, response, backend_index)
                continue

            if response is not None and (response.status_code >= 200 and response.status_code <= 399):
                return self._handle_200_399_response(request, response, backend_index)

            return self._handle_4xx_response(request, response)

        # Since no backends are available, we must return a 429.
        return self._return_429()
