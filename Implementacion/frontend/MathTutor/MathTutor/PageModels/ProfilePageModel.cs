using CommunityToolkit.Mvvm.ComponentModel;
using CommunityToolkit.Mvvm.Input;
using MathTutor.Services;
using System.Collections.ObjectModel;
using System.Linq;
using System.Threading.Tasks;
using Microsoft.Maui.Controls;

namespace MathTutor.PageModels
{
    public partial class ProfilePageModel : ObservableObject
    {
        private readonly ProblemService _problemService;
        private readonly SessionService _sessionService;

        [ObservableProperty] private int completedProblems;
        [ObservableProperty] private int totalProblems;
        [ObservableProperty] private string accuracyPct = "60%";
        [ObservableProperty] private int streak = 5;
        [ObservableProperty]
        private ObservableCollection<TopicProgress> topicProgress = new ObservableCollection<TopicProgress>();

        public ProfilePageModel(ProblemService problemService, SessionService sessionService)
        {
            _problemService = problemService;
            _sessionService = sessionService;
        }

        [RelayCommand]
        private Task Appearing()
        {
            // TODO: Fetch real stats from your backend (user history).
            CompletedProblems = 12;
            TotalProblems = 20;
            AccuracyPct = "60%";
            Streak = 5;
            TopicProgress.Clear();
            TopicProgress.Add(new TopicProgress("Álgebra", 0.8, "Excelente dominio"));
            TopicProgress.Add(new TopicProgress("Geometría", 0.6, "En progreso"));
            TopicProgress.Add(new TopicProgress("Probabilidad", 0.4, "Necesita práctica"));
            return Task.CompletedTask;
        }

        [RelayCommand]
        private async Task RepeatInterests()
        {
            // Resolve a Page instance without using the obsolete Application.MainPage.
            var app = Application.Current;
            var page = app?.Windows?.FirstOrDefault()?.Page;
            if (page == null)
            {
                // No page available - nothing to display
                return;
            }

            await page.DisplayAlertAsync("Intereses", "Repetir cuestionario de intereses...", "OK");
        }
    }

    public record TopicProgress(string TopicName, double Progress, string ProgressMessage);
}
