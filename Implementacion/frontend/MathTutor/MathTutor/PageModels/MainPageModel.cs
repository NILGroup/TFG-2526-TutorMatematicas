using CommunityToolkit.Mvvm.ComponentModel;
using CommunityToolkit.Mvvm.Input;

using MathTutor.Models;
using MathTutor.Services;
using System.Collections.ObjectModel;
using System.Linq;
using System.Diagnostics;

namespace MathTutor.PageModels
{
    public partial class MainPageModel : ObservableObject
    {
        private readonly ProblemService _problemService;
        private readonly SessionService _sessionService;

        [ObservableProperty]
        private ObservableCollection<ProblemOut> recommendedProblems = new();

        [ObservableProperty]
        private bool hasSession;

        private string? _sessionId;

        public MainPageModel(ProblemService problemService,
                             SessionService sessionService)
        {
            _problemService = problemService;
            _sessionService = sessionService;
        }

        [RelayCommand]
        private async Task Appearing()
        {
            // Start or refresh the daily session
            var response = await _sessionService.StartSessionAsync(
                new StartSessionRequest { UserId = "user123", K = 5 });

            if (response?.ProblemIds != null)
            {
                _sessionId = response.SessionId;
                HasSession = true;
                RecommendedProblems.Clear();
                foreach (string id in response.ProblemIds)
                {
                    var prob = await _problemService.GetProblemByIdAsync(id);
                    if (prob != null) RecommendedProblems.Add(prob);
                }
            }
        }

        [RelayCommand]
        private async Task ContinueSession()
        {
            // Safely obtain a current Page from Application windows and use the async API.
            var page = Application.Current?.Windows.FirstOrDefault()?.Page;
            if (page != null)
            {
                await page.DisplayAlertAsync("Sesión", "Continuar la sesión...", "OK");
            }
            else
            {
                Debug.WriteLine("ContinueSession: no current Page available to display alert.");
            }
        }

        [RelayCommand]
        private async Task StartProblem(string id)
        {
            // Safely obtain a current Page from Application windows and use the async API.
            var page = Application.Current?.Windows.FirstOrDefault()?.Page;
            if (page != null)
            {
                await page.DisplayAlertAsync("Seleccionado", $"Abrir problema: {id}", "OK");
            }
            else
            {
                Debug.WriteLine($"StartProblem: no current Page available to display alert for id={id}.");
            }
        }
    }
}