# Chạy script này để cập nhật IP lên DuckDNS
# Thay YOUR_TOKEN bằng token của bạn ở trang duckdns.org

$token  = "YOUR_TOKEN_HERE"
$domain = "sicbo"

$url = "https://www.duckdns.org/update?domains=$domain&token=$token&ip="
$response = Invoke-WebRequest -Uri $url -UseBasicParsing
Write-Output "$(Get-Date) - DuckDNS update: $($response.Content)"
