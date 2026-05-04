using MathTutor.Models;
using System.Collections.Generic;
using System.Threading.Tasks;
using System.Web;

namespace MathTutor.Services
{
    public class ProblemService
    {
        private readonly ApiService _api;

        public ProblemService(ApiService api) => _api = api;

        public Task<List<ProblemOut>?> GetProblemsAsync(
            string? course = null, string? kc = null, string? tag = null,
            int? difficulty = null, int limit = 20, int skip = 0)
        {
            var query = new List<string>();

            if (!string.IsNullOrWhiteSpace(course))
                query.Add($"course={Uri.EscapeDataString(course)}");

            if (!string.IsNullOrWhiteSpace(kc))
                query.Add($"kc={Uri.EscapeDataString(kc)}");

            if (!string.IsNullOrWhiteSpace(tag))
                query.Add($"tag={Uri.EscapeDataString(tag)}");

            if (difficulty.HasValue)
                query.Add($"difficulty={difficulty.Value}");

            query.Add($"limit={limit}");
            query.Add($"skip={skip}");

            return _api.GetAsync<List<ProblemOut>>($"/problems?{string.Join("&", query)}");
        }

        public Task<ProblemOut?> GetProblemByIdAsync(string id)
            => _api.GetAsync<ProblemOut>($"/problems/{id}");

        public Task<ProblemDetailOut?> GetProblemDetailAsync(string id)
            => _api.GetAsync<ProblemDetailOut>($"/problems/{id}");
    }
}
