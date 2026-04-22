using System;
using System.Net.Http;
using System.Text;
using System.Text.Json;
using System.Threading.Tasks;

namespace MathTutor
{
    public class ApiService
    {
        private readonly HttpClient _client;
        private readonly JsonSerializerOptions _jsonOptions =
            new() { PropertyNameCaseInsensitive = true };

        public ApiService(string baseUrl)
        {
            _client = new HttpClient { BaseAddress = new Uri(baseUrl) };
        }

        // Generic GET helper
        public async Task<T?> GetAsync<T>(string path)
        {
            using HttpResponseMessage resp = await _client.GetAsync(path);
            resp.EnsureSuccessStatusCode();
            string json = await resp.Content.ReadAsStringAsync();
            return JsonSerializer.Deserialize<T>(json, _jsonOptions);
        }

        // Generic POST helper
        public async Task<T?> PostAsync<T>(string path, object payload)
        {
            string jsonPayload = JsonSerializer.Serialize(payload);
            using HttpResponseMessage resp = await _client.PostAsync(
                path,
                new StringContent(jsonPayload, Encoding.UTF8, "application/json")
            );
            resp.EnsureSuccessStatusCode();
            string json = await resp.Content.ReadAsStringAsync();
            return JsonSerializer.Deserialize<T>(json, _jsonOptions);
        }
    }
}

/* Example of usage in vew model:
 * 
 * 
// Suppose you initialize ApiService with your backend URL
var api = new ApiService("http://localhost:8000");
var problemService = new ProblemService(api);
var sessionService = new SessionService(api);
var tutorService   = new TutorService(api);

// 1) Get a list of problems
var problems = await problemService.GetProblemsAsync(course: "2º ESO", limit: 10);

// 2) Start a session for a user
var startReq = new StartSessionRequest { UserId = "user123", K = 5, Course = "2º ESO" };
var session = await sessionService.StartSessionAsync(startReq);

// 3) Show first problem in UI and collect user answer, then submit attempt
var problemId = session.ProblemIds[0];
// … user interacts, answers the question …
var attemptReq = new AttemptRequest
{
    UserId = "user123",
    ProblemId = problemId,
    IsCorrect = true, // or false
    StudentAnswer = "42",
    SecondsSpent = 90
};
var attemptResp = await sessionService.SubmitAttemptAsync(session.SessionId, attemptReq);

// 4) User asks a clarifying question about the current problem
var chatReq = new TutorChatRequest
{
    ProblemId = problemId,
    Question = "¿Cómo aplico la regla del producto en este caso?",
    UserId = "user123",
    CurrentAttempt = "Calculo derivadas por separado"
};
var chatResp = await tutorService.AskQuestionAsync(chatReq);
// chatResp.Answer contains the model’s Spanish explanation
 
 */