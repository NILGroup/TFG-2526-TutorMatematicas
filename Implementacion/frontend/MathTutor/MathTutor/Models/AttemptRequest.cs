using System.Text.Json.Serialization;

namespace MathTutor.Models
{
    public class AttemptRequest
    {
        [JsonPropertyName("user_id")]
        public string UserId { get; set; } = string.Empty;

        [JsonPropertyName("problem_id")]
        public string ProblemId { get; set; } = string.Empty;

        [JsonPropertyName("is_correct")]
        public bool IsCorrect { get; set; }

        [JsonPropertyName("student_answer")]
        public string? StudentAnswer { get; set; }

        [JsonPropertyName("seconds_spent")]
        public int? SecondsSpent { get; set; }
    }
}