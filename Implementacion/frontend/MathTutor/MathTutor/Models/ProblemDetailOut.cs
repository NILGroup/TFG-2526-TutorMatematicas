using System.Text.Json.Serialization;

namespace MathTutor.Models
{
    public class ProblemDetailOut
    {
        [JsonPropertyName("id")]
        public string Id { get; set; } = string.Empty;

        [JsonPropertyName("course")]
        public string? Course { get; set; }

        [JsonPropertyName("kc")]
        public string? Kc { get; set; }

        [JsonPropertyName("tags")]
        public List<string> Tags { get; set; } = new();

        [JsonPropertyName("difficulty")]
        public int? Difficulty { get; set; }

        [JsonPropertyName("statement")]
        public string Statement { get; set; } = string.Empty;

        [JsonPropertyName("rendered_statement")]
        public string RenderedStatement { get; set; } = string.Empty;

        [JsonPropertyName("parameters")]
        public Dictionary<string, object> Parameters { get; set; } = new();

        [JsonPropertyName("instantiated_parameters")]
        public Dictionary<string, int> InstantiatedParameters { get; set; } = new();

        [JsonPropertyName("solution_steps")]
        public List<string> SolutionSteps { get; set; } = new();

        [JsonPropertyName("answer")]
        public string? Answer { get; set; }
    }
}
