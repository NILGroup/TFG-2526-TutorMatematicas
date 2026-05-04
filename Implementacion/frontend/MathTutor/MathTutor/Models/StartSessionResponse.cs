using System.Collections.Generic;
using System.Text.Json.Serialization;

namespace MathTutor.Models
{
    public class StartSessionResponse
    {
        [JsonPropertyName("session_id")]
        public string SessionId { get; set; } = "";

        [JsonPropertyName("problem_ids")]
        public List<string> ProblemIds { get; set; } = new();
    }
}