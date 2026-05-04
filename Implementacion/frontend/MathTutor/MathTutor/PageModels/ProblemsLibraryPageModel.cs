using CommunityToolkit.Mvvm.ComponentModel;
using CommunityToolkit.Mvvm.Input;
using MathTutor.Models;
using MathTutor.Services;
using System.Collections.ObjectModel;

namespace MathTutor.PageModels
{
    public partial class ProblemsLibraryPageModel : ObservableObject
    {
        private readonly ProblemService _problemService;

        // Full list returned by the API — text search is applied client-side
        private List<ProblemOut> _allProblems = new();

        // Sentinel used by the Picker to mean "no filter".
        // The Picker can't bind directly to null, so we round-trip via the
        // SelectedCourseDisplay property below.
        private const string AllCoursesLabel = "Todos";

        public ObservableCollection<ProblemOut> Problems { get; } = new();

        [ObservableProperty]
        [NotifyPropertyChangedFor(nameof(ResultsLabel))]
        private string searchQuery = string.Empty;

        [ObservableProperty]
        [NotifyPropertyChangedFor(nameof(SelectedCourseDisplay))]
        [NotifyPropertyChangedFor(nameof(ResultsLabel))]
        private string? selectedCourse;

        [ObservableProperty]
        [NotifyPropertyChangedFor(nameof(ResultsLabel))]
        private string? selectedKc;

        [ObservableProperty]
        [NotifyPropertyChangedFor(nameof(DifficultyDisplay))]
        [NotifyPropertyChangedFor(nameof(ResultsLabel))]
        private int? selectedDifficulty;

        [ObservableProperty] private bool isLoading;

        // ── Computed ──────────────────────────────────────────────────────────
        public string DifficultyDisplay => SelectedDifficulty?.ToString() ?? "—";
        public string ResultsLabel =>
            $"{Problems.Count} problema{(Problems.Count != 1 ? "s" : "")} encontrado{(Problems.Count != 1 ? "s" : "")}";

        // ── Picker options (with the "Todos" sentinel) ────────────────────────
        public List<string> CourseOptionsWithAll { get; } =
            new() { AllCoursesLabel, "1º ESO", "2º ESO", "3º ESO", "4º ESO", "1º Bach", "2º Bach" };

        // The Picker binds to this. It maps "Todos" ↔ null so the user can
        // actually clear the course filter from the UI.
        public string SelectedCourseDisplay
        {
            get => SelectedCourse ?? AllCoursesLabel;
            set
            {
                var newValue = (value == AllCoursesLabel || string.IsNullOrWhiteSpace(value))
                    ? null
                    : value;
                if (newValue != SelectedCourse)
                    SelectedCourse = newValue;
            }
        }

        // KcOptions is intentionally empty — the backend has no endpoint that
        // returns the full taxonomy. Populate this from a discovery call when needed.
        public List<string> KcOptions { get; } = new();

        public ProblemsLibraryPageModel(ProblemService problemService)
        {
            _problemService = problemService;
        }

        // ── Lifecycle ─────────────────────────────────────────────────────────

        [RelayCommand]
        private async Task Appearing() => await LoadFromApiAsync();

        // ── Property change reactions ─────────────────────────────────────────

        // SearchQuery → client-side filter only (no API round-trip)
        partial void OnSearchQueryChanged(string oldValue, string newValue) => ApplySearch();

        // Filter changes require a new API call
        partial void OnSelectedCourseChanged(string? oldValue, string? newValue) => _ = LoadFromApiAsync();
        partial void OnSelectedKcChanged(string? oldValue, string? newValue) => _ = LoadFromApiAsync();
        partial void OnSelectedDifficultyChanged(int? oldValue, int? newValue) => _ = LoadFromApiAsync();

        // ── Difficulty stepper commands ───────────────────────────────────────

        [RelayCommand]
        private void IncreaseDifficulty()
        {
            SelectedDifficulty = SelectedDifficulty is null ? 1 : Math.Min(5, SelectedDifficulty.Value + 1);
        }

        [RelayCommand]
        private void DecreaseDifficulty()
        {
            if (SelectedDifficulty is null) return;
            SelectedDifficulty = SelectedDifficulty.Value <= 1 ? null : SelectedDifficulty.Value - 1;
        }

        // ── Navigation ────────────────────────────────────────────────────────

        [RelayCommand]
        private async Task OpenProblem(string id)
        {
            if (string.IsNullOrWhiteSpace(id)) return;
            await Shell.Current.GoToAsync($"ProblemDetailPage?problemId={Uri.EscapeDataString(id)}");
        }

        // ── Data loading ──────────────────────────────────────────────────────

        private async Task LoadFromApiAsync()
        {
            IsLoading = true;
            try
            {
                var list = await _problemService.GetProblemsAsync(
                    course: string.IsNullOrWhiteSpace(SelectedCourse) ? null : SelectedCourse,
                    kc: string.IsNullOrWhiteSpace(SelectedKc) ? null : SelectedKc,
                    tag: null,
                    difficulty: SelectedDifficulty,
                    limit: 100);

                _allProblems = list ?? new List<ProblemOut>();
                ApplySearch();
            }
            finally
            {
                IsLoading = false;
            }
        }

        /// <summary>
        /// Filters _allProblems by SearchQuery and refreshes the Problems collection.
        /// Matches against rendered statement, KC name, and tag names.
        /// </summary>
        private void ApplySearch()
        {
            Problems.Clear();

            var q = SearchQuery?.Trim();
            IEnumerable<ProblemOut> filtered = string.IsNullOrEmpty(q)
                ? _allProblems
                : _allProblems.Where(p =>
                    p.RenderedStatement.Contains(q, StringComparison.OrdinalIgnoreCase) ||
                    (p.Kc?.Contains(q, StringComparison.OrdinalIgnoreCase) == true) ||
                    p.Tags.Any(t => t.Contains(q, StringComparison.OrdinalIgnoreCase)));

            foreach (var p in filtered)
                Problems.Add(p);

            OnPropertyChanged(nameof(ResultsLabel));
        }
    }
}
