using MathTutor.Models;
using System.Threading.Tasks;

namespace MathTutor.Services
{
    public class UserService
    {
        private readonly ApiService _api;

        public UserService(ApiService api)
        {
            _api = api;
        }

        public async Task<UserProfileResponse?> GetUserAsync(string userId)
        {
            return await _api.GetAsync<UserProfileResponse>($"/users/{userId}");
        }

        public async Task<bool> UpdateInterestsAsync(string userId, UserInterestsRequest payload)
        {
            var result = await _api.PutAsync<ApiOkResponse>($"/users/{userId}/interests", payload);
            return result?.Ok == true;
        }
    }

    public class ApiOkResponse
    {
        public bool Ok { get; set; }
    }
}