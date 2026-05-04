using CommunityToolkit.Mvvm.ComponentModel;
using CommunityToolkit.Mvvm.Input;
using MathTutor.Models;
using MathTutor.Services;
using System.Collections.ObjectModel;

namespace MathTutor.PageModels
{
    public partial class ProblemDetailPageModel : ObservableObject, IQueryAttributable
    {
        // ── Dependencies ──────────────────────────────────────────────────
        private readonly ProblemService _problemService;
        private readonly TutorService _tutorService;
        private readonly SessionService _sessionService;

        // ── Loading state ─────────────────────────────────────────────────

        [ObservableProperty]
        [NotifyPropertyChangedFor(nameof(IsNotLoading))]
        private bool isLoading = false;

        public bool IsNotLoading => !IsLoading;

        // ── Problem ───────────────────────────────────────────────────────

        [ObservableProperty]
        [NotifyPropertyChangedFor(nameof(HasMoreHints))]
        [NotifyPropertyChangedFor(nameof(HasAnyHints))]
        private ProblemDetailOut? problem;

        [ObservableProperty] private string? sessionId;

        private string UserId => Preferences.Default.Get("user_id", "user_default");

        // ── Answer flow ──────────────────────────────────────────────────

        [ObservableProperty]
        [NotifyPropertyChangedFor(nameof(IsAnswerPhase))]
        [NotifyPropertyChangedFor(nameof(IsAssessmentPhase))]
        private bool answerSubmitted = false;

        [ObservableProperty]
        private string answerText = string.Empty;

        private DateTime _problemStartTime = DateTime.UtcNow;

        // ── Self-assessment ──────────────────────────────────────────────

        [ObservableProperty]
        [NotifyPropertyChangedFor(nameof(HasResult))]
        [NotifyPropertyChangedFor(nameof(IsAnswerCorrect))]
        [NotifyPropertyChangedFor(nameof(IsAssessmentPhase))]
        [NotifyPropertyChangedFor(nameof(ResultMessage))]
        private bool? lastAnswerCorrect = null;

        public bool IsAnswerPhase => !AnswerSubmitted;
        public bool IsAssessmentPhase => AnswerSubmitted && !LastAnswerCorrect.HasValue;
        public bool HasResult => LastAnswerCorrect.HasValue;
        public bool IsAnswerCorrect => LastAnswerCorrect == true;

        public string ResultMessage => LastAnswerCorrect == true
            ? "¡Correcto! Bien hecho."
            : "Incorrecto. ¡Sigue practicando!";

        /// <summary>The expected answer — last solution step, exposed in the assessment phase.</summary>
        public string ExpectedAnswer =>
            Problem?.SolutionSteps.LastOrDefault() ?? Problem?.Answer ?? "(no disponible)";

        // ── Hints (reveal one solution step at a time) ───────────────────

        public ObservableCollection<string> RevealedHints { get; } = new();

        public bool HasAnyHints => Problem?.SolutionSteps?.Count > 0;

        /// <summary>
        /// True when at least one unrevealed solution step remains. The last
        /// solution step is the final answer; we don't reveal it as a hint
        /// (it's shown as ExpectedAnswer once the user has submitted).
        /// </summary>
        public bool HasMoreHints
        {
            get
            {
                if (Problem?.SolutionSteps is null) return false;
                // Treat the last step as the answer, not a hint.
                int hintCount = Math.Max(0, Problem.SolutionSteps.Count - 1);
                return RevealedHints.Count < hintCount;
            }
        }

        // ── Chat ──────────────────────────────────────────────────────────

        [ObservableProperty]
        [NotifyPropertyChangedFor(nameof(ChatToggleText))]
        private bool isChatVisible = false;

        [ObservableProperty]
        private string chatInput = string.Empty;

        [ObservableProperty]
        [NotifyPropertyChangedFor(nameof(IsNotSendingMessage))]
        private bool isSendingMessage = false;

        public bool IsNotSendingMessage => !IsSendingMessage;
        public string ChatToggleText => IsChatVisible ? "✕" : "?";

        public ObservableCollection<ChatMessage> ChatMessages { get; } = new();

        public event EventHandler? ScrollToLastMessage;

        // ── Constructor ───────────────────────────────────────────────────

        public ProblemDetailPageModel(
            ProblemService problemService,
            TutorService tutorService,
            SessionService sessionService)
        {
            _problemService = problemService;
            _tutorService = tutorService;
            _sessionService = sessionService;

            // Recompute HasMoreHints whenever the revealed list changes.
            RevealedHints.CollectionChanged += (_, _) => OnPropertyChanged(nameof(HasMoreHints));
        }

        // ── Shell navigation ──────────────────────────────────────────────

        public void ApplyQueryAttributes(IDictionary<string, object> query)
        {
            if (query.TryGetValue("problemId", out var pid) && pid is string problemId)
                _ = LoadProblemAsync(problemId);

            if (query.TryGetValue("sessionId", out var sid) && sid is string sId)
                SessionId = sId;
        }

        // ── Load ──────────────────────────────────────────────────────────

        private async Task LoadProblemAsync(string problemId)
        {
            IsLoading = true;

            // Reset all per-problem state
            AnswerText = string.Empty;
            AnswerSubmitted = false;
            LastAnswerCorrect = null;
            IsChatVisible = false;
            ChatMessages.Clear();
            RevealedHints.Clear();
            _problemStartTime = DateTime.UtcNow;

            try
            {
                Problem = await _problemService.GetProblemDetailAsync(problemId);
                OnPropertyChanged(nameof(ExpectedAnswer));
            }
            finally
            {
                IsLoading = false;
            }
        }

        // ── Answer flow ──────────────────────────────────────────────────

        [RelayCommand]
        private void SubmitAnswer()
        {
            if (string.IsNullOrWhiteSpace(AnswerText) || Problem is null)
                return;
            // Move to self-assessment phase.  ExpectedAnswer becomes visible.
            AnswerSubmitted = true;
            OnPropertyChanged(nameof(ExpectedAnswer));
        }

        [RelayCommand]
        private async Task MarkCorrect() => await RecordAttemptAsync(isCorrect: true);

        [RelayCommand]
        private async Task MarkIncorrect() => await RecordAttemptAsync(isCorrect: false);

        private async Task RecordAttemptAsync(bool isCorrect)
        {
            LastAnswerCorrect = isCorrect;

            if (SessionId is null || Problem is null)
                return;

            var elapsed = (int)(DateTime.UtcNow - _problemStartTime).TotalSeconds;

            try
            {
                await _sessionService.SubmitAttemptAsync(SessionId, new AttemptRequest
                {
                    UserId = UserId,
                    ProblemId = Problem.Id,
                    IsCorrect = isCorrect,
                    StudentAnswer = AnswerText,
                    SecondsSpent = elapsed,
                });
            }
            catch
            {
                // BKT update failure should not block the UI.
            }
        }

        // ── Hints ─────────────────────────────────────────────────────────

        /// <summary>
        /// Reveals the next unread solution step as a hint. Each press shows
        /// one more step; once all hints are revealed the button disables.
        /// The final solution step (= the answer) is NOT revealed here — it
        /// shows up as ExpectedAnswer in the assessment phase.
        /// </summary>
        [RelayCommand]
        private void RequestHint()
        {
            if (Problem?.SolutionSteps is null) return;
            if (!HasMoreHints) return;

            RevealedHints.Add(Problem.SolutionSteps[RevealedHints.Count]);
        }

        // ── Chat ──────────────────────────────────────────────────────────

        [RelayCommand]
        private void ToggleChat() => IsChatVisible = !IsChatVisible;

        /// <summary>
        /// Send the contents of <see cref="ChatInput"/> to the tutor service.
        ///
        /// Returns Task (not async void) so the [RelayCommand] generator emits
        /// a proper IAsyncRelayCommand. Early-returns silently when the input
        /// is empty or a previous request is still in flight, so double-taps
        /// don't queue duplicate messages.
        /// </summary>
        [RelayCommand]
        private async Task SendChatMessage()
        {
            var text = (ChatInput ?? string.Empty).Trim();
            if (string.IsNullOrEmpty(text) || Problem is null || IsSendingMessage)
                return;

            ChatInput = string.Empty;
            await SendTutorMessageAsync(userText: text, currentAttempt: null);
        }

        private async Task SendTutorMessageAsync(string userText, string? currentAttempt)
        {
            if (Problem is null) return;

            // 1) Student bubble
            ChatMessages.Add(new ChatMessage { IsUser = true, Text = userText });
            ScrollToLastMessage?.Invoke(this, EventArgs.Empty);

            // 2) Placeholder tutor bubble + busy flag
            var tutorMsg = new ChatMessage { IsUser = false, Text = "…" };
            ChatMessages.Add(tutorMsg);
            ScrollToLastMessage?.Invoke(this, EventArgs.Empty);
            IsSendingMessage = true;

            try
            {
                var req = new TutorChatRequest
                {
                    ProblemId = Problem.Id,
                    Question = userText,
                    UserId = UserId,
                    CurrentAttempt = currentAttempt,
                    RenderedStatement = Problem.RenderedStatement,
                };

                var response = await _tutorService.AskQuestionAsync(req);
                var fullText = response?.Answer ?? "No se pudo obtener una respuesta.";

                await TypewriterAsync(tutorMsg, fullText);
            }
            catch (Exception ex)
            {
                tutorMsg.Text = $"Error al contactar al tutor: {ex.Message}";
            }
            finally
            {
                IsSendingMessage = false;
                ScrollToLastMessage?.Invoke(this, EventArgs.Empty);
            }
        }

        private static async Task TypewriterAsync(ChatMessage message, string fullText, int delayMs = 14)
        {
            message.Text = string.Empty;
            var sb = new System.Text.StringBuilder(fullText.Length);
            foreach (char c in fullText)
            {
                sb.Append(c);
                message.Text = sb.ToString();
                await Task.Delay(delayMs);
            }
        }
    }
}
