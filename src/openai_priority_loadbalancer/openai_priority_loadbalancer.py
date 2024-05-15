"""Module providing a prioritized load-balancing for Azure OpenAI."""

import logging
import random
import traceback
from typing import List
from datetime import datetime, MAXYEAR, MINYEAR, timedelta, timezone
from dateutil.tz import tzutc
from httpx import AsyncClient, Client, Response

class Backend:
    """Class representing a backend object used with Azure OpenAI, etc."""

    # Constructor
    def __init__(self, host: str, priority: int):
        self.host = host
        self.priority = priority
        self.is_throttling = False
        self.retry_after = datetime.min
        self.successful_call_count = 0

# Reference design at https://github.com/encode/httpx/blob/master/httpx/_transports/base.py
# BaseLoadBalancer providing functionality to both synchronous and asynchronous load balancers
class BaseLoadBalancer():
    """Logically abstract Base Load Balancer class that should be inherited"""

    # Constructor
    def __init__(self, transport, backends: List[Backend]):
        self._transport = transport
        self.backends = backends
        self._backend_index = -1
        self._remaining_backends = 1
        self._log = logging.getLogger("openai-priority-loadbalancer")     # https://www.loggly.com/ultimate-guide/python-logging-basics/

    # "Protected" Methods
    def _check_throttling(self):
        min_datetime = datetime(MINYEAR, 1, 1, tzinfo = tzutc())

        for backend in self.backends:
            if backend.is_throttling and datetime.now(tzutc()) >= backend.retry_after:
                backend.is_throttling = False
                backend.retry_after = min_datetime
                self._log.info("Backend %s is no longer throttling.", backend.host)

    def _get_backend_index(self):
        # This is the main logic to pick the backend to be used
        selected_priority = float('inf')
        available_backends = []

        # Evaluate all defined backends for availability and priority, leaving only the most-desirable available backends from which to select.
        for i, backend in enumerate(self.backends):
            if not backend.is_throttling:
                backend_priority = backend.priority

                if backend_priority < selected_priority:
                    selected_priority = backend_priority
                    available_backends.clear()
                    available_backends.append(i)
                elif backend_priority == selected_priority:
                    available_backends.append(i)

        if len(available_backends) == 1:
            return available_backends[0]

        if len(available_backends) > 0:
            # Since this code is very likely being called from multiple python instances with multiple workers in parallel executions, there's no way to distribute requests uniformly across all Azure OpenAI instances.
            # Doing so would require a centralized service, cache, etc. to keep track of a common backends list, but that would also imply a locking mechanism for updates, which would
            # immediately inhibit the performance benefits of the load balancer. This is why this is more of a pseudo load-balancer. Therefore, we'll just randomize across the available backends.
            return random.choice(available_backends)
        else:
            # If there are no available backends, -1 will be returned to indicate that nothing is available (and that we consequently need to bail by returning an HTTP 429).
            return -1

    def _get_remaining_backends(self):
        self._remaining_backends = 0

        for backend in self.backends:
            if not backend.is_throttling:
                self._remaining_backends += 1

        return self._remaining_backends

    def _get_soonest_retry_after(self):
        soonest_retry_after = datetime(MAXYEAR, 1, 1, tzinfo = tzutc())

        for backend in self.backends:
            if backend.is_throttling and backend.retry_after < soonest_retry_after:
                soonest_retry_after = backend.retry_after
                soonest_backend = backend.host

        delay = int((soonest_retry_after - datetime.now(timezone.utc)).total_seconds()) + 1     # Add a 1 second buffer to ensure we don't retry too early
        self._log.info("Soonest Retry After: %s - %s second(s)", soonest_backend, str(delay))
        return delay

    def _handle_200_399_response(self, request, response, backend_index):
        # Successful requests
        self._log.info("Request sent to server: %s, Status code: %s", request.url, response.status.code)
        self.backends[backend_index].successful_call_count += 1

    def _handle_429_5xx_response(self, request, response, backend_index):
        # If the server is throttling or there's a server error, retry with a different server
        self._log.info("Request sent to server: %s, Status code: %s - FAIL", request.url, response.status.code)

        retry_after = int(response.headers.get('Retry-After', '-1'))

        if retry_after == -1:
            retry_after = int(response.headers.get('x-ratelimit-reset-requests', '-1'))

        if retry_after == -1:
            retry_after = int(response.headers.get('x-ratelimit-reset-requests', '10'))

        self._log.info("Backend %s is throttling. Retry after %s second(s).", self.backends[backend_index].host, retry_after)

        backend = self.backends[backend_index]
        backend.is_throttling = True
        backend.retry_after = datetime.now(tzutc()) + timedelta(seconds = retry_after)
        self._get_remaining_backends()

    def _handle_4xx_response(self, request, response):
        # Would likely be a 4xx error other than 429
        self._log.warning("Request sent to server: %s, Status code: %s - FAIL", request.url, response.status_code)

    def _modify_request(self, request, backend_index):
        # Modify the request. Note that only the URL and Host header are being modified on the original request object. We make the smallest incision possible to avoid side effects.
        # Update URL and host header as both must match the backend server.
        request.url = request.url.copy_with(host = self.backends[backend_index].host)
        request.headers = request.headers.copy()    # Create a mutable copy of the headers
        request.headers['host'] = self.backends[backend_index].host

    def _return_429(self):
        self._log.warning("No backend available!")
        retry_after = str(self._get_soonest_retry_after())
        self._log.info("Returning HTTP 429 with Retry-After header value of %s second(s).", retry_after)
        return Response(429, content = '', headers={'Retry-After': retry_after})

class AsyncLoadBalancer(BaseLoadBalancer):
    """Asynchronous Load Balancer class based on BaseLoadBalancer"""

    # Constructor
    def __init__(self, backends: List[Backend]):
        super().__init__(AsyncClient(), backends)

    # Public Methods
    async def handle_async_request(self, request):
        """Handles an asynchronous request by issuing an asynchronous request to an available backed."""

        self._check_throttling()
        self._get_remaining_backends()
        response = None

        while True and self._remaining_backends > 0:
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

            # 4) Evaluate the response from the backend
            if response is not None and (response.status_code == 429 or response.status_code >= 500):
                self._handle_429_5xx_response(request, response, backend_index)
                continue

            elif response is not None and (response.status_code >= 200 and response.status_code <= 399):
                self._handle_200_399_response(request, response, backend_index)
                break

            else:
                self._handle_4xx_response(request, response)
                break

        if self._remaining_backends == 0:
            return self._return_429()

        return response

class LoadBalancer(BaseLoadBalancer):
    """Synchronous Load Balancer class based on BaseLoadBalancer"""

    # Constructor
    def __init__(self, backends: List[Backend]):
        super().__init__(Client(), backends)

    # Public Methods
    def handle_request(self, request):
        """Handles a synchronous request by issuing a request to an available backed."""

        self._check_throttling()
        self._get_remaining_backends()
        response = None

        while True and self._remaining_backends > 0:
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

            # 4) Evaluate the response from the backend
            if response is not None and (response.status_code == 429 or response.status_code >= 500):
                self._handle_429_5xx_response(request, response, backend_index)
                continue

            elif response is not None and (response.status_code >= 200 and response.status_code <= 399):
                self._handle_200_399_response(request, response, backend_index)
                break

            else:
                self._handle_4xx_response(request, response)
                break

        if self._remaining_backends == 0:
            return self._return_429()

        return response
