using CommunityToolkit.Mvvm.ComponentModel;
using CommunityToolkit.Mvvm.Input;

using MathTutor.Models;
using MathTutor.Services;
using System.Collections.ObjectModel;
using System.Diagnostics;

namespace MathTutor.PageModels
{
    public partial class MainPageModel : ObservableObject
    {
        private readonly ProblemService _problemService;
        private readonly SessionService _sessionService;

        // UserId is hard-coded for now; replace with auth once available
        private const string DefaultUserId = "user123";

        [ObservableProperty]
        private ObservableCollection<ProblemOut> recommendedProblems = new();

        [ObservableProperty]
        private bool hasSession;

        [ObservableProperty]
        private bool isBusy;

        [ObservableProperty]
        private string? errorMessage;

        /// <summary>True when we are showing the empty pre-generation state.</summary>
        public bool ShowEmptyState => !HasSession && !IsBusy;

        private string? _sessionId;

        public MainPageModel(ProblemService problemService,
                             SessionService sessionService)
        {
            _problemService = problemService;
            _sessionService = sessionService;
        }

        // When HasSession or IsBusy changes, recompute ShowEmptyState
        partial void OnHasSessionChanged(bool value) => OnPropertyChanged(nameof(ShowEmptyState));
        partial void OnIsBusyChanged(bool value) => OnPropertyChanged(nameof(ShowEmptyState));

        // ────────────────────────────────────────────────────────────────
        // No auto-generation on Appearing — the user controls when to
        // request a new session via the "Generar sesión" button.
        // ────────────────────────────────────────────────────────────────
        [RelayCommand]
        private Task Appearing() => Task.CompletedTask;

        [RelayCommand]
        private async Task StartProblem(string id)
        {
            if (string.IsNullOrWhiteSpace(id)) return;

            var route = $"ProblemDetailPage?problemId={Uri.EscapeDataString(id)}";
            if (!string.IsNullOrWhiteSpace(_sessionId))
                route += $"&sessionId={Uri.EscapeDataString(_sessionId)}";

            await Shell.Current.GoToAsync(route);
        }

        [RelayCommand]
        private async Task GenerateSession()
        {
            if (IsBusy) return;

            IsBusy = true;
            ErrorMessage = null;

            try
            {
                var response = await _sessionService.StartSessionAsync(
                    new StartSessionRequest { UserId = DefaultUserId, K = 5 });

                RecommendedProblems.Clear();

                if (response?.ProblemIds != null && response.ProblemIds.Count > 0)
                {
                    _sessionId = response.SessionId;

                    foreach (var id in response.ProblemIds)
                    {
                        var prob = await _problemService.GetProblemByIdAsync(id);
                        if (prob != null)
                            RecommendedProblems.Add(prob);
                    }

                    HasSession = RecommendedProblems.Count > 0;
                }
                else
                {
                    HasSession = false;
                    ErrorMessage = "El servidor no devolvió problemas. Comprueba tus preferencias.";
                }
            }
            catch (Exception ex)
            {
                HasSession = false;
                ErrorMessage = "No se pudo conectar con el servidor.";
                Debug.WriteLine($"GenerateSession failed: {ex}");
            }
            finally
            {
                IsBusy = false;
            }
        }
    }
}
