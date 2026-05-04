using CommunityToolkit.Maui.Alerts;
using CommunityToolkit.Maui.Core;
using MathTutor.Pages;
using Font = Microsoft.Maui.Font;

namespace MathTutor
{
    public partial class AppShell : Shell
    {
        public AppShell()
        {
            InitializeComponent();

            // ─────────────────────────────────────────────────────────────
            // Register routes for pages that aren't in the tab bar but can
            // be reached via Shell.Current.GoToAsync(...).
            //
            // Without this, GoToAsync silently fails — the navigation never
            // happens and there is no exception, which is why tapping
            // a problem card or "Modificar mis preferencias" did nothing.
            // ─────────────────────────────────────────────────────────────
            Routing.RegisterRoute(nameof(ProblemDetailPage), typeof(ProblemDetailPage));
            Routing.RegisterRoute(nameof(QuestionnairePage), typeof(QuestionnairePage));

            var currentTheme = Application.Current!.RequestedTheme;
        }

        public static async Task DisplaySnackbarAsync(string message)
        {
            CancellationTokenSource cancellationTokenSource = new CancellationTokenSource();

            var snackbarOptions = new SnackbarOptions
            {
                BackgroundColor = Color.FromArgb("#FF3300"),
                TextColor = Colors.White,
                ActionButtonTextColor = Colors.Yellow,
                CornerRadius = new CornerRadius(0),
                Font = Font.SystemFontOfSize(18),
                ActionButtonFont = Font.SystemFontOfSize(14)
            };

            var snackbar = Snackbar.Make(message, visualOptions: snackbarOptions);

            await snackbar.Show(cancellationTokenSource.Token);
        }

        public static async Task DisplayToastAsync(string message)
        {
            if (OperatingSystem.IsWindows())
                return;

            var toast = Toast.Make(message, textSize: 18);

            var cts = new CancellationTokenSource(TimeSpan.FromSeconds(5));
            await toast.Show(cts.Token);
        }

        private void SfSegmentedControl_SelectionChanged(object? sender, Syncfusion.Maui.Toolkit.SegmentedControl.SelectionChangedEventArgs e)
        {
            Application.Current!.UserAppTheme = e.NewIndex == 0 ? AppTheme.Light : AppTheme.Dark;
        }
    }
}
