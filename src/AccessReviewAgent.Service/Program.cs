using AccessReviewAgent.Service;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Hosting;

AgentPathsBootstrap.Init();

Host.CreateDefaultBuilder(args)
    .UseWindowsService(options => options.ServiceName = "AccessReviewAgent")
    .ConfigureServices(services => services.AddHostedService<AgentWorker>())
    .Build()
    .Run();

namespace AccessReviewAgent.Service
{
    internal static class AgentPathsBootstrap
    {
        public static void Init() => AccessReviewAgent.Shared.AgentPaths.EnsureDirectory();
    }
}
