using MathTutor.Models;
using System.Threading.Tasks;

namespace MathTutor.Services
{
    public class SessionService
    {
        private readonly ApiService _api;
        public SessionService(ApiService api) => _api = api;

        public Task<StartSessionResponse?> StartSessionAsync(StartSessionRequest req)
            => _api.PostAsync<StartSessionResponse>("/sessions/start", req);

        public Task<AttemptResponse?> SubmitAttemptAsync(string sessionId, AttemptRequest req)
            => _api.PostAsync<AttemptResponse>($"/sessions/{sessionId}/attempt", req);

        public Task<Dictionary<string, object>?> GetSessionAsync(string sessionId)
            => _api.GetAsync<Dictionary<string, object>>($"/sessions/{sessionId}");
    }
}
