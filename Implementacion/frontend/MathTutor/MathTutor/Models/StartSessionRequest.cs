using System.Text.Json.Serialization;

namespace MathTutor.Models
{
    public class StartSessionRequest
    {
        [JsonPropertyName("user_id")]
        public string UserId { get; set; } = "";

        [JsonPropertyName("k")]
        public int K { get; set; }

        [JsonPropertyName("course")]
        public string? Course { get; set; }
    }
}