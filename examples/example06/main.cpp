
#include <iostream>
#include <curl/curl.h>

using namespace std;

int main() {
    cout << "CRAB rulez!!" << endl;

    CURL *curl;
    CURLcode res;

    curl = curl_easy_init();
    if(curl) {
        curl_easy_setopt(curl, CURLOPT_CAINFO, "./ca-bundle.crt");

        curl_easy_setopt(curl, CURLOPT_URL, "https://example.com");
        /* example.com is redirected, so we tell libcurl to follow
            redirection */ 
        curl_easy_setopt(curl, CURLOPT_FOLLOWLOCATION, 1L);

        /* Disable hostname certificate verification (because
            https://example.com has an invalid certificate - yeah, go figure) */
        curl_easy_setopt(curl, CURLOPT_SSL_VERIFYHOST, 0L);

        /* Perform the request, res will get the return code */ 
        res = curl_easy_perform(curl);
        /* Check for errors */ 
        if(res != CURLE_OK)
            fprintf(stderr, "curl_easy_perform() failed: %s\n",
                    curl_easy_strerror(res));

        /* always cleanup */ 
        curl_easy_cleanup(curl);
    }

    cout << "CRAB rulez!!" << endl;

    return 0;
}

