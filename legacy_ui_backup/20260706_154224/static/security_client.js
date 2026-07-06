(function () {
    "use strict";

    const originalFetch = window.fetch.bind(
        window
    );

    const unsafeMethods = new Set([
        "POST",
        "PUT",
        "PATCH",
        "DELETE",
    ]);


    function getCookie(name) {
        const prefix = `${name}=`;

        const cookie = document.cookie
            .split(";")
            .map((item) => item.trim())
            .find((item) => {
                return item.startsWith(prefix);
            });

        if (!cookie) {
            return "";
        }

        return decodeURIComponent(
            cookie.slice(prefix.length)
        );
    }


    window.fetch = async function (
        input,
        init = {}
    ) {
        const sourceRequest = (
            input instanceof Request
                ? input
                : null
        );

        const requestUrl = new URL(
            sourceRequest
                ? sourceRequest.url
                : input,
            window.location.href
        );

        const method = String(
            init.method
            || sourceRequest?.method
            || "GET"
        ).toUpperCase();

        if (
            requestUrl.origin
            === window.location.origin
            && unsafeMethods.has(method)
        ) {
            const headers = new Headers(
                init.headers
                || sourceRequest?.headers
                || {}
            );

            const csrfToken = getCookie(
                "docurapi_csrf"
            );

            if (csrfToken) {
                headers.set(
                    "X-CSRF-Token",
                    csrfToken
                );
            }

            if (sourceRequest) {
                input = new Request(
                    sourceRequest,
                    {
                        ...init,
                        headers,
                    }
                );

                init = undefined;
            }
            else {
                init = {
                    ...init,
                    headers,
                };
            }
        }

        return originalFetch(
            input,
            init
        );
    };


    window.DocuRapiSecurity = {
        getCsrfToken() {
            return getCookie(
                "docurapi_csrf"
            );
        },

        async refreshCsrf() {
            const response = await originalFetch(
                "/api/security/csrf"
            );

            return response.json();
        },
    };
})();