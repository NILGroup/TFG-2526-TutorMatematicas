using CommunityToolkit.Maui;
using Microsoft.Extensions.Logging;
using Syncfusion.Maui.Toolkit.Hosting;

namespace MathTutor
{
    public static class MauiProgram
    {
        public static MauiApp CreateMauiApp()
        {
            var builder = MauiApp.CreateBuilder();
            builder
                .UseMauiApp<App>()
                .UseMauiCommunityToolkit()
                .ConfigureSyncfusionToolkit()
                .ConfigureMauiHandlers(handlers =>
                {
#if WINDOWS
    				Microsoft.Maui.Controls.Handlers.Items.CollectionViewHandler.Mapper.AppendToMapping("KeyboardAccessibleCollectionView", (handler, view) =>
    				{
    					handler.PlatformView.SingleSelectionFollowsFocus = false;
    				});
#endif
                })
                .ConfigureFonts(fonts =>
                {
                    fonts.AddFont("OpenSans-Regular.ttf", "OpenSansRegular");
                    fonts.AddFont("OpenSans-Semibold.ttf", "OpenSansSemibold");
                    fonts.AddFont("SegoeUI-Semibold.ttf", "SegoeSemibold");
                    fonts.AddFont("FluentSystemIcons-Regular.ttf", FluentUI.FontFamily);
                })
                .Services.AddSingleton<ApiService>(sp =>
                new ApiService("localhost:8000"));

#if DEBUG
            builder.Logging.AddDebug();
    		builder.Services.AddLogging(configure => configure.AddDebug());
#endif

            // Register domain services
            builder.Services.AddSingleton<ProblemService>();
            builder.Services.AddSingleton<SessionService>();
            builder.Services.AddSingleton<TutorService>();

            // Register PageModels
            builder.Services.AddSingleton<MainPageModel>();
            builder.Services.AddSingleton<ProblemsLibraryPageModel>();
            builder.Services.AddSingleton<ProfilePageModel>();
            builder.Services.AddSingleton<SettingsPageModel>();

            // Register pages
            builder.Services.AddTransient<MainPage>();
            builder.Services.AddTransient<ProblemsLibraryPage>();
            builder.Services.AddTransient<ProfilePage>();
            builder.Services.AddTransient<SettingsPage>();

            return builder.Build();
        }
    }
}
