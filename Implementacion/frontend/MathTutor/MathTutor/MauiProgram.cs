using CommunityToolkit.Maui;
using Microsoft.Extensions.Logging;
using Syncfusion.Maui.Toolkit.Hosting;
using Microsoft.Maui.Devices;

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
                });

            // Backend URL varies by platform
            string baseUrl = DeviceInfo.Platform == DevicePlatform.Android
                ? "http://10.0.2.2:8000"
                : "http://127.0.0.1:8000";
            builder.Services.AddSingleton(sp => new ApiService(baseUrl));

#if DEBUG
            builder.Logging.AddDebug();
            builder.Services.AddLogging(configure => configure.AddDebug());
#endif

            // ── Services ─────────────────────────────────────────────
            builder.Services.AddSingleton<ProblemService>();
            builder.Services.AddSingleton<SessionService>();
            builder.Services.AddSingleton<TutorService>();
            builder.Services.AddSingleton<UserService>();

            // ── Page models ──────────────────────────────────────────
            builder.Services.AddSingleton<MainPageModel>();
            builder.Services.AddSingleton<ProblemsLibraryPageModel>();
            builder.Services.AddSingleton<ProblemDetailPageModel>();
            builder.Services.AddSingleton<ProfilePageModel>();
            builder.Services.AddSingleton<SettingsPageModel>();
            // Questionnaire is transient — each launch starts fresh
            builder.Services.AddTransient<QuestionnairePageModel>();

            // ── Pages ────────────────────────────────────────────────
            builder.Services.AddSingleton<MainPage>();
            builder.Services.AddSingleton<ProblemsLibraryPage>();
            builder.Services.AddTransient<ProblemDetailPage>();
            builder.Services.AddSingleton<ProfilePage>();
            builder.Services.AddSingleton<SettingsPage>();
            builder.Services.AddTransient<QuestionnairePage>();

            return builder.Build();
        }
    }
}
