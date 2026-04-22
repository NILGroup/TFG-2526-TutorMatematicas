using MathTutor.Models;
using System.Threading.Tasks;

namespace MathTutor.Services
{
    public class TutorService
    {
        private readonly ApiService _api;
        public TutorService(ApiService api) => _api = api;

        public Task<TutorChatResponse?> AskQuestionAsync(TutorChatRequest req)
            => _api.PostAsync<TutorChatResponse>("/tutor/chat", req);
    }
}
