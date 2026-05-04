using System.Collections.Generic;
using System.Text.Json.Serialization;

namespace MathTutor.Models
{
    public class TutorChatResponse
    {
        [JsonPropertyName("answer")]
        public string Answer { get; set; } = "";

        [JsonPropertyName("meta")]
        public Dictionary<string, object>? Meta { get; set; }
    }
}