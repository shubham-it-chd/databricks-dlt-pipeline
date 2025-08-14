Enabling HTTP/3 in ASP.NET Core

In .NET 8, enabling HTTP/3 in an ASP.NET Core application is more streamlined and fully supported out of the box. Here's a concise guide tailored specifically for .NET 8:

✅ Requirements for .NET 8

    .NET Version: .NET 8 (HTTP/3 is fully supported)

Operating System:

    ✅ Windows 11 / Windows Server 2022

    ✅ Linux with libmsquic

    ❌ macOS is still not supported due to SecureTransport limitations



TLS Certificate: Required for HTTP/3 (TLS 1.3)

MsQuic: Automatically used by Kestrel if available



⚙️ Steps to Enable HTTP/3 in .NET 8



1. Install .NET 8 SDK

    Download from dotnet.microsoft.com/download



2. Configure Kestrel in Program.cs



        using Microsoft.AspNetCore.Server.Kestrel.Core;

        var builder = WebApplication.CreateBuilder(args);

        builder.WebHost.ConfigureKestrel(options =>
        {
            options.ListenAnyIP(5001, listenOptions =>
            {

                listenOptions.Protocols = HttpProtocols.Http1AndHttp2AndHttp3;

                listenOptions.UseHttps(); // Use a valid TLS certificate
            });

        });

        var app = builder.Build();

        app.Use((context, next) =>
        {
            context.Response.Headers.AltSvc = "h3=\":5001\"";

            return next(context);
        });

        app.MapGet("/", () => "Hello from HTTP/3!");

        app.Run();



3. No Need for Preview Flags

    Unlike .NET 6, you do not need to enable preview features in .csproj.



4. TLS Certificate Setup

    For development:

        dotnet dev-certs https --trust

        

    For production:

        listenOptions.UseHttps("certificate.pfx", "yourPassword");



5. Install MsQuic on Linux
    ```sh
    sudo apt update

    sudo apt install libmsquic
    ```
        



6. Testing HTTP/3

    ✅ Browser

    Use Chrome, Edge, or Firefox. Check the protocol in DevTools → Network tab.



    ✅ HttpClient

        using System.Net;

        var client = new HttpClient
        {
            DefaultRequestVersion = HttpVersion.Version30,

            DefaultVersionPolicy = HttpVersionPolicy.RequestVersionOrLower
        };

        var response = await client.GetAsync("https://localhost:5001/");

        Console.WriteLine($"Status: {response.StatusCode}, Version: {response.Version}");



7. Logging

   Add to appsettings.json:

        {

            "Logging": {

                "LogLevel": {

                "Default": "Information",

                "Microsoft.AspNetCore": "Warning",

                "Microsoft.AspNetCore.Hosting.Diagnostics": "Information"

                }

            }

        }





8. To Enabled TLS on server

# Enable TLS 1.3 on Local System
    ```sh
    New-Item 'HKLM:\SYSTEM\CurrentControlSet\Control\SecurityProviders\SCHANNEL\Protocols\TLS 1.3\Client' -Force

    New-Item 'HKLM:\SYSTEM\CurrentControlSet\Control\SecurityProviders\SCHANNEL\Protocols\TLS 1.3\Server' -Force

    New-ItemProperty -Path 'HKLM:\SYSTEM\CurrentControlSet\Control\SecurityProviders\SCHANNEL\Protocols\TLS 1.3\Client' -Name 'Enabled' -Value 1 -PropertyType 'DWORD'

    New-ItemProperty -Path 'HKLM:\SYSTEM\CurrentControlSet\Control\SecurityProviders\SCHANNEL\Protocols\TLS 1.3\Client' -Name 'DisabledByDefault' -Value 0 -PropertyType 'DWORD'

    New-ItemProperty -Path 'HKLM:\SYSTEM\CurrentControlSet\Control\SecurityProviders\SCHANNEL\Protocols\TLS 1.3\Server' -Name 'Enabled' -Value 1 -PropertyType 'DWORD'

    New-ItemProperty -Path 'HKLM:\SYSTEM\CurrentControlSet\Control\SecurityProviders\SCHANNEL\Protocols\TLS 1.3\Server' -Name 'DisabledByDefault' -Value 0 -PropertyType 'DWORD'

    # Enable HTTP/3 for IIS (optional)
    New-ItemProperty -Path 'HKLM:\SYSTEM\CurrentControlSet\Services\HTTP\Parameters' -Name 'EnableHttp3' -Value 1 -PropertyType 'DWORD'
    ```

8. Troubleshooting

✅ Check browser support and Alt-Svc header

✅ Trust development certificate:

✅ dotnet dev-certs https --trust

✅ Review Kestrel logs for MsQuic or protocol issues

✅ HTTP/3 fallback to HTTP/2 or HTTP/1.1