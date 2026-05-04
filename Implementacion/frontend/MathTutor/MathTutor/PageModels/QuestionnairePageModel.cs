using CommunityToolkit.Mvvm.ComponentModel;
using CommunityToolkit.Mvvm.Input;
using MathTutor.Models;
using MathTutor.Services;
using System.Collections.ObjectModel;

namespace MathTutor.PageModels
{
    /// <summary>
    /// Multi-step preferences questionnaire.
    ///
    /// Steps:
    ///   0  Curso              (course level)
    ///   1  Objetivo           (primary objective)
    ///   2  Cursos cercanos    (allow_cross_course)
    ///   3  Dificultad         (target difficulty)
    ///   4  Intereses por KC   (kc_scores)
    ///
    /// The KC list is discovered at runtime from the problems collection
    /// (we pull a sample of problems and extract unique `kc` values),
    /// so no backend change is required.
    ///
    /// On completion, payload is sent via PUT /users/{id}/interests.
    /// </summary>
    public partial class QuestionnairePageModel : ObservableObject
    {
        private readonly UserService _userService;
        private readonly ProblemService _problemService;

        private const string DefaultUserId = "user123";
        private const int TotalSteps = 5;

        // ── Step navigation ──────────────────────────────────────────────

        [ObservableProperty]
        [NotifyPropertyChangedFor(nameof(StepIndicator))]
        [NotifyPropertyChangedFor(nameof(IsStep0))]
        [NotifyPropertyChangedFor(nameof(IsStep1))]
        [NotifyPropertyChangedFor(nameof(IsStep2))]
        [NotifyPropertyChangedFor(nameof(IsStep3))]
        [NotifyPropertyChangedFor(nameof(IsStep4))]
        [NotifyPropertyChangedFor(nameof(IsFirstStep))]
        [NotifyPropertyChangedFor(nameof(IsLastStep))]
        [NotifyPropertyChangedFor(nameof(ProgressFraction))]
        [NotifyPropertyChangedFor(nameof(NextButtonText))]
        private int currentStep;

        public bool IsStep0 => CurrentStep == 0;
        public bool IsStep1 => CurrentStep == 1;
        public bool IsStep2 => CurrentStep == 2;
        public bool IsStep3 => CurrentStep == 3;
        public bool IsStep4 => CurrentStep == 4;

        public bool IsFirstStep => CurrentStep == 0;
        public bool IsLastStep => CurrentStep == TotalSteps - 1;

        public string StepIndicator => $"Paso {CurrentStep + 1} de {TotalSteps}";
        public double ProgressFraction => (double)(CurrentStep + 1) / TotalSteps;
        public string NextButtonText => IsLastStep ? "Finalizar" : "Siguiente";

        // ── Step 0 — Course ──────────────────────────────────────────────

        public List<string> CourseOptions { get; } = new()
        {
            "1º ESO", "2º ESO", "3º ESO", "4º ESO", "1º Bach", "2º Bach"
        };

        [ObservableProperty] private string selectedCourse = "1º ESO";

        // ── Step 1 — Objective ───────────────────────────────────────────

        public List<ObjectiveOption> ObjectiveOptions { get; } = new()
        {
            new("PRACTICE",          "Practicar",           "Una mezcla equilibrada de problemas."),
            new("IMPROVE_GRADES",    "Mejorar notas",       "Más enfoque en tus puntos débiles."),
            new("REVIEW",            "Repasar",             "Diversidad alta, menos exploración."),
            new("LEARN_NEW_CONTENT", "Aprender nuevo",      "Más temas nuevos y dificultad creciente."),
        };

        [ObservableProperty] private ObjectiveOption? selectedObjective;

        // ── Step 2 — Allow cross-course ──────────────────────────────────

        [ObservableProperty] private bool allowCrossCourse;

        // ── Step 3 — Target difficulty ───────────────────────────────────

        [ObservableProperty]
        [NotifyPropertyChangedFor(nameof(TargetDifficultyLabel))]
        private int targetDifficulty = 3;

        public string TargetDifficultyLabel => TargetDifficulty switch
        {
            1 => "1 — Muy fácil",
            2 => "2 — Fácil",
            3 => "3 — Medio",
            4 => "4 — Difícil",
            5 => "5 — Muy difícil",
            _ => $"{TargetDifficulty}",
        };

        // ── Step 4 — KC ratings ──────────────────────────────────────────

        public ObservableCollection<KcRatingItem> KcRatings { get; } = new();

        [ObservableProperty] private bool isKcListLoading;

        // ── Global state ─────────────────────────────────────────────────

        [ObservableProperty] private bool isSaving;
        [ObservableProperty] private string? errorMessage;

        public QuestionnairePageModel(UserService userService, ProblemService problemService)
        {
            _userService = userService;
            _problemService = problemService;

            // Default selected objective
            SelectedObjective = ObjectiveOptions[0];
        }

        [RelayCommand]
        private async Task Appearing()
        {
            // Prefill from existing user profile if available
            await PrefillFromUserAsync();
            // Load the KC list in the background so it's ready for step 4
            await LoadKcListAsync();
        }

        [RelayCommand]
        private void NextStep()
        {
            if (CurrentStep < TotalSteps - 1)
                CurrentStep++;
            else
                _ = SaveAsync();
        }

        [RelayCommand]
        private void PreviousStep()
        {
            if (CurrentStep > 0)
                CurrentStep--;
        }

        // ── Prefill ──────────────────────────────────────────────────────

        private async Task PrefillFromUserAsync()
        {
            try
            {
                var user = await _userService.GetUserAsync(DefaultUserId);
                if (user == null) return;

                if (!string.IsNullOrWhiteSpace(user.Profile?.CourseLevel))
                    SelectedCourse = user.Profile.CourseLevel;

                var objectiveCode = user.Interests?.PrimaryObjective;
                var match = ObjectiveOptions.FirstOrDefault(o => o.Code == objectiveCode);
                if (match != null) SelectedObjective = match;

                AllowCrossCourse = user.Profile?.AllowCrossCourse ?? false;

                if (user.Interests?.DifficultyPreferences?.TargetDifficulty is int td && td >= 1 && td <= 5)
                    TargetDifficulty = td;

                // Preserve existing KC scores when we populate the list later
                _prefilledKcScores = user.Interests?.KcScores ?? new Dictionary<string, float>();
            }
            catch (Exception ex)
            {
                System.Diagnostics.Debug.WriteLine($"Prefill failed: {ex}");
            }
        }

        private Dictionary<string, float> _prefilledKcScores = new();

        // ── Dynamic KC list ──────────────────────────────────────────────

        /// <summary>
        /// Pulls a batch of problems from the backend and extracts the
        /// unique <c>kc</c> values, producing a list of ratings initialised
        /// to the user's existing scores (or 3 for unseen KCs).
        /// </summary>
        private async Task LoadKcListAsync()
        {
            if (KcRatings.Count > 0) return;   // already loaded

            IsKcListLoading = true;
            try
            {
                var problems = await _problemService.GetProblemsAsync(limit: 200);

                var uniqueKcs = (problems ?? new())
                    .Where(p => !string.IsNullOrWhiteSpace(p.Kc))
                    .Select(p => p.Kc!)
                    .Distinct(StringComparer.OrdinalIgnoreCase)
                    .OrderBy(k => k, StringComparer.OrdinalIgnoreCase)
                    .ToList();

                foreach (var kc in uniqueKcs)
                {
                    var initialScore = _prefilledKcScores.TryGetValue(kc, out var s)
                        ? (int)Math.Round(s)
                        : 3;
                    KcRatings.Add(new KcRatingItem(kc, initialScore));
                }
            }
            catch (Exception ex)
            {
                System.Diagnostics.Debug.WriteLine($"LoadKcList failed: {ex}");
            }
            finally
            {
                IsKcListLoading = false;
            }
        }

        // ── Save ─────────────────────────────────────────────────────────

        private async Task SaveAsync()
        {
            if (IsSaving) return;

            IsSaving = true;
            ErrorMessage = null;

            try
            {
                var payload = new UserInterestsRequest
                {
                    UserId = DefaultUserId,
                    CourseLevel = SelectedCourse,
                    PrimaryObjective = SelectedObjective?.Code ?? "PRACTICE",
                    AllowCrossCourse = AllowCrossCourse,
                    DifficultyPreferences = new DifficultyPreferences
                    {
                        MinDifficulty = Math.Max(1, TargetDifficulty - 1),
                        MaxDifficulty = Math.Min(5, TargetDifficulty + 1),
                        TargetDifficulty = TargetDifficulty,
                        Trend = "STABLE",
                    },
                    SessionPreferences = new SessionPreferences
                    {
                        ProblemsPerSession = 5,
                        SessionsPerWeek = 4,
                    },
                    ProblemPreferences = new ProblemPreferences(),
                };

                foreach (var item in KcRatings)
                    payload.KcScores[item.KcKey] = item.Score;

                var ok = await _userService.UpdateInterestsAsync(DefaultUserId, payload);
                if (!ok)
                {
                    ErrorMessage = "No se pudieron guardar las preferencias.";
                    return;
                }

                if (Shell.Current != null)
                {
                    var page = Application.Current?.Windows.FirstOrDefault()?.Page;
                    if (page != null)
                        await page.DisplayAlert("Preferencias guardadas",
                            "Tus recomendaciones se actualizarán en tu próxima sesión.", "OK");

                    await Shell.Current.GoToAsync("..");
                }
            }
            catch (Exception ex)
            {
                ErrorMessage = "Error al conectar con el servidor.";
                System.Diagnostics.Debug.WriteLine($"Save questionnaire failed: {ex}");
            }
            finally
            {
                IsSaving = false;
            }
        }
    }

    // ─────────────────────────────────────────────────────────────────────
    // Helper records / items
    // ─────────────────────────────────────────────────────────────────────

    public record ObjectiveOption(string Code, string DisplayName, string Description);

    public partial class KcRatingItem : ObservableObject
    {
        public string KcKey { get; }

        [ObservableProperty]
        [NotifyPropertyChangedFor(nameof(ScoreLabel))]
        private int score;

        public string ScoreLabel => Score switch
        {
            1 => "Muy bajo",
            2 => "Bajo",
            3 => "Medio",
            4 => "Alto",
            5 => "Muy alto",
            _ => $"{Score}",
        };

        public KcRatingItem(string kcKey, int score)
        {
            KcKey = kcKey;
            this.score = score;
        }
    }
}
