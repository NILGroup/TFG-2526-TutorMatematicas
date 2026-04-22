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

        public ObservableCollection<ProblemOut> Problems { get; } = new();

        [ObservableProperty] private string searchQuery;
        [ObservableProperty] private string selectedCourse;
        [ObservableProperty] private string selectedKc;
        [ObservableProperty] private int selectedDifficulty = 3;

        public List<string> CourseOptions { get; } =
            new() { "1º ESO", "2º ESO", "3º ESO", "4º ESO", "1º Bach", "2º Bach" };
        public List<string> KcOptions { get; } =
            new() { "Álgebra", "Geometría", "Funciones", "Estadística" };

        public ProblemsLibraryPageModel(ProblemService problemService)
        {
            _problemService = problemService;
        }

        [RelayCommand]
        private async Task Appearing()
        {
            await LoadProblemsAsync();
        }

        partial void OnSearchQueryChanged(string oldValue, string newValue)
        {
            _ = LoadProblemsAsync();
        }
        partial void OnSelectedCourseChanged(string oldValue, string newValue)
        {
            _ = LoadProblemsAsync();
        }
        partial void OnSelectedKcChanged(string oldValue, string newValue)
        {
            _ = LoadProblemsAsync();
        }
        partial void OnSelectedDifficultyChanged(int oldValue, int newValue)
        {
            _ = LoadProblemsAsync();
        }

        private async Task LoadProblemsAsync()
        {
            var list = await _problemService.GetProblemsAsync(
                course: SelectedCourse, kc: SelectedKc,
                tag: null, difficulty: SelectedDifficulty);

            Problems.Clear();
            if (list != null)
            {
                foreach (var p in list) Problems.Add(p);
            }
        }
    }
}
