using CommunityToolkit.Mvvm.ComponentModel;
using CommunityToolkit.Mvvm.Input;
using MathTutor.Models;
using MathTutor.Services;

namespace MathTutor.PageModels
{
    /// <summary>
    /// Profile summary page.
    ///
    /// Shows the user's current preferences and progress statistics, and
    /// provides a single entry point to edit preferences via the
    /// QuestionnairePage.  Direct preference editing has been removed from
    /// this page — the questionnaire is the canonical flow.
    /// </summary>
    public partial class ProfilePageModel : ObservableObject
    {
        private readonly UserService _userService;
        internal const string DefaultUserId = "user123";

        // ── Profile summary (read-only display) ──────────────────────────

        [ObservableProperty] private string courseLevel = "—";
        [ObservableProperty] private string primaryObjective = "—";
        [ObservableProperty] private bool allowCrossCourse;
        [ObservableProperty] private int targetDifficulty;
        [ObservableProperty] private int problemsPerSession;

        // ── Progress stats ───────────────────────────────────────────────

        [ObservableProperty] private int totalAttempts;
        [ObservableProperty] private int correctAttempts;
        [ObservableProperty] private int streak;

        /// <summary>Success rate 0–100 as string, or "—" when no attempts.</summary>
        public string AccuracyDisplay =>
            TotalAttempts > 0
                ? $"{(int)Math.Round(100.0 * CorrectAttempts / TotalAttempts)}%"
                : "—";

        // Re-compute derived value whenever its inputs change
        partial void OnTotalAttemptsChanged(int value) => OnPropertyChanged(nameof(AccuracyDisplay));
        partial void OnCorrectAttemptsChanged(int value) => OnPropertyChanged(nameof(AccuracyDisplay));

        [ObservableProperty] private bool isLoading;

        public ProfilePageModel(UserService userService)
        {
            _userService = userService;
        }

        [RelayCommand]
        private async Task Appearing() => await LoadProfileAsync();

        [RelayCommand]
        private async Task Refresh() => await LoadProfileAsync();

        [RelayCommand]
        private async Task OpenQuestionnaire()
        {
            await Shell.Current.GoToAsync("QuestionnairePage");
        }

        private async Task LoadProfileAsync()
        {
            IsLoading = true;
            try
            {
                var user = await _userService.GetUserAsync(DefaultUserId);
                if (user == null) return;

                CourseLevel = user.Profile?.CourseLevel ?? "—";
                PrimaryObjective = FormatObjective(user.Interests?.PrimaryObjective);
                AllowCrossCourse = user.Profile?.AllowCrossCourse ?? false;
                TargetDifficulty = user.Interests?.DifficultyPreferences?.TargetDifficulty ?? 0;
                ProblemsPerSession = user.Interests?.SessionPreferences?.ProblemsPerSession ?? 0;

                TotalAttempts = user.Progress?.TotalAttempts ?? 0;
                CorrectAttempts = user.Progress?.CorrectAttempts ?? 0;
                Streak = user.Progress?.Streak ?? 0;
            }
            catch (Exception ex)
            {
                System.Diagnostics.Debug.WriteLine($"Profile load failed: {ex}");
            }
            finally
            {
                IsLoading = false;
            }
        }

        /// <summary>Humanises the objective code for display.</summary>
        private static string FormatObjective(string? code) => code switch
        {
            "PRACTICE" => "Práctica",
            "IMPROVE_GRADES" => "Mejorar notas",
            "REVIEW" => "Repaso",
            "LEARN_NEW_CONTENT" => "Aprender contenido nuevo",
            _ => "—",
        };
    }
}
