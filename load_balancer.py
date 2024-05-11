from datetime import datetime, MINYEAR, MAXYEAR, timedelta, timezone
from dateutil.tz import tzutc
from httpx import Client, Response, BaseTransport
from typing import List
import random
import traceback

class Backend:
    def __init__(self, host: str, priority: int):
        self.host = host
        self.priority = priority
        self.is_throttling = False
        self.retry_after = datetime.min
        self.successful_call_count = 0

class LoadBalancer(BaseTransport):
    # Constructor
    def __init__(self, backends: List[Backend]):
        self._transport = Client()
        self.backends = backends
        self._backend_index = -1
        self._remaining_backends = 1

    # Private Methods
    def _check_throttling(self):
        min_datetime = datetime(MINYEAR, 1, 1, tzinfo=tzutc())

        for backend in self.backends:
            if backend.is_throttling and datetime.now(tzutc()) >= backend.retry_after:
                backend.is_throttling = False
                backend.retry_after = min_datetime
                print(f"{datetime.now()}:   Backend {backend.host} is no longer throttling.")

    def _get_backend_index(self):
        # This is the main logic to pick the backend to be used
        selected_priority = float('inf')
        available_backends = []

        for i in range(len(self.backends)):
            backend = self.backends[i]

            if not backend.is_throttling:
                backendPriority = backend.priority

                if backendPriority < selected_priority:
                    selected_priority = backendPriority
                    available_backends.clear()
                    available_backends.append(i)
                elif backendPriority == selected_priority:
                    available_backends.append(i)

        if len(available_backends) == 1:
            return available_backends[0]

        if len(available_backends) > 0:
            # Since this code is very likely being called from multiple python instances with multiple workers in parallel executions, there's no way to distribute requests uniformly across all Azure OpenAI instances.
            # Doing so would require a centralized service, cache, etc. to keep track of a common backends list, but that would also imply a locking mechanism for updates, which would
            # immediately inhibit the performance benefits of the load balancer. This is why this is more of a pseudo load-balancer. Therefore, we'll just randomize across the available backends.
            return random.choice(available_backends)
        else:
            # If there are no available Backend, -1 will be returned to indicate that nothing is available (and that we should bail).
            return -1

    def _get_remaining_backends(self):
        self._remaining_backends = 0

        for backend in self.backends:
            if not backend.is_throttling:
                self._remaining_backends += 1

        return self._remaining_backends

    def _get_soonest_retry_after(self):
        soonest_retry_after = datetime(MAXYEAR, 1, 1, tzinfo=tzutc())

        for backend in self.backends:
            if backend.is_throttling and backend.retry_after < soonest_retry_after:
                soonest_retry_after = backend.retry_after
                soonest_backend = backend.host

        delay = int((soonest_retry_after - datetime.now(timezone.utc)).total_seconds()) + 1     # Add a 1 second buffer to ensure we don't retry too early
        print(f"{datetime.now()}:   Soonest Retry After: {soonest_backend} - {str(delay)} second(s)")

        return delay

    def _return_429(self):
        print(f"{datetime.now()}:   No backend available!")
        retry_after = str(self._get_soonest_retry_after())
        print(f"{datetime.now()}:   Returning HTTP 429 with Retry-After header value of {retry_after} second(s).")
        return Response(429, content='', headers={'Retry-After': retry_after})

    # Public Methods
    def handle_request(self, request):
        self._check_throttling()
        self._get_remaining_backends()
        response = None

        while True and self._remaining_backends > 0:
            backend_index = self._get_backend_index()

            if backend_index == -1:
                return self._return_429()

            # Update URL and host header
            request.url = request.url.copy_with(host=self.backends[backend_index].host)
            headers = request.headers.copy()    # Create a mutable copy of the headers
            headers['host'] = self.backends[backend_index].host
            request.headers = headers           # Assign the modified headers back to request.headers

            # Send the request to the backend
            try:
                response = self._transport.send(request)
            except Exception as e:
                traceback.print_exc()

            if response is not None and (response.status_code == 429 or response.status_code >= 500):
                # If the server is throttling or there's a server error, retry with a different server
                print(f"{datetime.now()}:   Request sent to server: {request.url}, Status Code: {response.status_code} - FAIL")
                retry_after = int(response.headers.get('Retry-After', '-1'))

                if retry_after == -1:
                    retry_after = int(response.headers.get('x-ratelimit-reset-requests', '-1'))

                if retry_after == -1:
                    retry_after = int(response.headers.get('x-ratelimit-reset-requests', '10'))

                print(f"{datetime.now()}:   Backend {self.backends[backend_index].host} is throttling. Retry after {retry_after} second(s).")

                backend = self.backends[backend_index]
                backend.is_throttling = True
                backend.retry_after = datetime.now(tzutc()) + timedelta(seconds=retry_after)
                self._get_remaining_backends()
                continue

            elif response is not None and (response.status_code >= 200 and response.status_code <= 399):
                # Successful requests
                print(f"{datetime.now()}:   Request sent to server: {request.url}, Status code: {response.status_code}")
                self.backends[backend_index].successful_call_count += 1
                break

            else:
                # Would likely be a 4xx error other than 429
                print(f"{datetime.now()}:   Request sent to server: {request.url}, Status code: {response.status_code} - FAIL")
                break

        if self._remaining_backends == 0:
            return self._return_429()

        return response
