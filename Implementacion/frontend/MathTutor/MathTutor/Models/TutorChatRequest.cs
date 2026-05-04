using System.Text.Json.Serialization;

namespace MathTutor.Models
{
    public class TutorChatRequest
    {
        [JsonPropertyName("problem_id")]
        public string ProblemId { get; set; } = "";

        [JsonPropertyName("question")]
        public string Question { get; set; } = "";

        [JsonPropertyName("user_id")]
        public string? UserId { get; set; }

        [JsonPropertyName("current_attempt")]
        public string? CurrentAttempt { get; set; }

        [JsonPropertyName("rendered_statement")]
        public string? RenderedStatement { get; set; }
    }
}