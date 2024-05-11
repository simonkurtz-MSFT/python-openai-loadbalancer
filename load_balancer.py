from datetime import datetime, MINYEAR, MAXYEAR, timedelta, timezone
from dateutil.tz import tzutc
from httpx import Client, Response, BaseTransport
from typing import List
import traceback

class Backend:
    def __init__(self, host: str, priority: int):
        self.host = host
        self.priority = priority
        self.is_throttling = False
        self.retry_after = datetime.min
        self.successful_call_count = 0

class LoadBalancer(BaseTransport):
    class Statistics:
        def __init__(self):
            self.reset_statistics()

        def reset_statistics(self):
            self.total_requests = 0     
            self.total_failures = 0
            self.total_successes = 0      
            self.backends_stats = {} 

        def update_backend_stats(self, host, success):
            if host not in self.backends_stats:
                self.backends_stats[host] = {'attempts': 0, 'successes': 0, 'failures': 0}
            if success:
                self.backends_stats[host]['attempts'] += 1
                self.backends_stats[host]['successes'] += 1
                self.total_successes += 1
            else:
                self.backends_stats[host]['attempts'] += 1
                self.backends_stats[host]['failures'] += 1
                self.total_failures += 1

            self.total_requests += 1

        def print(self):
            longest_host_string = len(max(self.backends_stats.keys(), key=len))
            repeater = longest_host_string + 48
            
            print("*" * repeater)
            pad = len(str(self.total_requests))    
            print(f"\nLoad Balancer Statistics: \n\nTotal Requests  : {str(self.total_requests).rjust(pad)}\nTotal Successes : {str(self.total_successes).rjust(pad)}\nTotal Failures  : {str(self.total_failures).rjust(pad)}\n")

            # Print the statistics per backend
            print(f"{'Backend':<{longest_host_string + 2}} {'Distribution %':<15} {'Attempts':<9} {'Successes':<10} {'Failures':<10}")
            print("-" * repeater)
            for host, stats in self.backends_stats.items():
                print(f"{host:<{longest_host_string + 2}} {round((stats['attempts'] * 100 / self.total_requests), 2):>14} {stats['attempts']:>9} {stats['successes']:>10} {stats['failures']:>9}")
            print("\n")
            print("*" * repeater)
    
    # Constructor
    def __init__(self, backends: List[Backend]):
        self._transport = Client()
        self.statistics = self.Statistics()
        self.backends = backends
        self._backendIndex = -1
        self._remainingBackend = 1        

    # Private Methods
    def _check_throttling(self):
        min_datetime = datetime(MINYEAR, 1, 1, tzinfo=tzutc())

        for backend in self.backends:
            if backend.is_throttling and datetime.now(tzutc()) >= backend.retry_after:
                backend.is_throttling = False
                backend.retry_after = min_datetime
                print(f"{datetime.now()}:   Backend {backend.host} is no longer throttling.")
    
    def _get_backendIndex(self):
        # This is the main logic to pick the backend to be used
        selected_priority = float('inf')
        available_Backend = []

        for i in range(len(self.backends)):
            backend = self.backends[i]

            if not backend.is_throttling:
                backendPriority = backend.priority

                if backendPriority < selected_priority:
                    selected_priority = backendPriority
                    available_Backend.clear()
                    available_Backend.append(i)
                elif backendPriority == selected_priority:
                    available_Backend.append(i)

        if len(available_Backend) == 1:
            return available_Backend[0]

        if len(available_Backend) > 0:
            # Select the backend with the lowest successful_call_count to achieve a more balanced distribution than what random.choice() could provide over a variable length array
            min_successful_call_count = self.backends[available_Backend[0]].successful_call_count
            selected_backend = available_Backend[0]

            for i in available_Backend[1:]:
                if self.backends[i].successful_call_count < min_successful_call_count:
                    min_successful_call_count = self.backends[i].successful_call_count
                    selected_backend = i

            return selected_backend            
        else:
            # If there are no available Backend, -1 will be returned to indicate that nothing is available (and that we should bail).
            return -1

    def _get_remainingBackend(self):
        self._remainingBackend = 0

        for backend in self.backends:
            if not backend.is_throttling:
                self._remainingBackend += 1

        return self._remainingBackend

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
        return self._return_429()

    # Public Methods
    def handle_request(self, request):
        self._check_throttling()
        self._get_remainingBackend()
        response = None
        
        while True and self._remainingBackend > 0:            
            backendIndex = self._get_backendIndex()
            
            if backendIndex == -1:
                print(f"{datetime.now()}:    No Backend available. Exiting.")             
                retryAfter = str(self._get_soonest_retry_after())                
                return Response(429, content='', headers={'Retry-After': retryAfter})
            
            # Update URL and host header
            request.url = request.url.copy_with(host=self.backends[backendIndex].host)                
            headers = request.headers.copy()    # Create a mutable copy of the headers
            headers['host'] = self.backends[backendIndex].host        
            request.headers = headers           # Assign the modified headers back to request.headers

            # Send the request to the backend
            try:
                response = self._transport.send(request)                
            except Exception as e:
                traceback.print_exc()

            if response is not None and (response.status_code == 429 or response.status_code >= 500):                
                # If the server is throttling or there's a server error, retry with a different server
                print(f"{datetime.now()}:   Request sent to server: {request.url}, Status Code: {response.status_code} - FAIL")
                self.statistics.update_backend_stats(self.backends[backendIndex].host, False)  # Request failed
                
                currentBackendIndex = backendIndex

                retryAfter = int(response.headers.get('Retry-After', '-1'))

                if retryAfter == -1:
                    retryAfter = int(response.headers.get('x-ratelimit-reset-requests', '-1'))

                if retryAfter == -1:
                    retryAfter = int(response.headers.get('x-ratelimit-reset-requests', '10'))

                print(f"{datetime.now()}:   Backend {self.backends[currentBackendIndex].host} is throttling. Retry after {retryAfter} second(s).")

                backend = self.backends[currentBackendIndex]
                backend.is_throttling = True
                backend.retry_after = datetime.now(tzutc()) + timedelta(seconds=retryAfter)
                self._get_remainingBackend()            
                continue

            elif response is not None and (response.status_code >= 200 and response.status_code <= 399):
                # Successful requests
                print(f"{datetime.now()}:   Request sent to server: {request.url}, Status code: {response.status_code}")
                self.backends[backendIndex].successful_call_count += 1
                self.statistics.update_backend_stats(self.backends[backendIndex].host, True)  # Request was successful
                break

            else:
                # Would likely be a 4xx error other than 429
                print(f"{datetime.now()}:   Request sent to server: {request.url}, Status code: {response.status_code} - FAIL")
                self.statistics.update_backend_stats(self.backends[backendIndex].host, False)  # Request failed
                break

        if self._remainingBackend == 0:
            return self._return_429()

        return response