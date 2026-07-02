# Exit 0 if ANPR dashboard responds on 127.0.0.1:8080, else exit 1.
$ErrorActionPreference = "SilentlyContinue"
try {
    $response = Invoke-WebRequest -Uri "http://127.0.0.1:8080/api/version" -UseBasicParsing -TimeoutSec 2
    if ($response.StatusCode -eq 200) {
        exit 0
    }
} catch {
}
exit 1
