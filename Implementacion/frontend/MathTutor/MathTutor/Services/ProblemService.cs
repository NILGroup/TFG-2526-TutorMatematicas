using MathTutor.Models;
using System.Collections.Generic;
using System.Threading.Tasks;

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
            // Build query string
            var query = new List<string>();
            if (!string.IsNullOrEmpty(course)) query.Add($"course={course}");
            if (!string.IsNullOrEmpty(kc)) query.Add($"kc={kc}");
            if (!string.IsNullOrEmpty(tag)) query.Add($"tag={tag}");
            if (difficulty.HasValue) query.Add($"difficulty={difficulty}");
            query.Add($"limit={limit}");
            query.Add($"skip={skip}");
            string q = string.Join("&", query);

            return _api.GetAsync<List<ProblemOut>>($"/problems?{q}");
        }

        public Task<ProblemOut?> GetProblemByIdAsync(string id)
            => _api.GetAsync<ProblemOut>($"/problems/{id}");
    }
}
