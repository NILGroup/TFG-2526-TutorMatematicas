using System.Collections.Generic;
using System.Text.Json.Serialization;

namespace MathTutor.Models
{
    public class AttemptResponse
    {
        [JsonPropertyName("ok")]
        public bool Ok { get; set; }

        [JsonPropertyName("kc")]
        public string? Kc { get; set; }

        [JsonPropertyName("p_know")]
        public double? PKnow { get; set; }

        [JsonPropertyName("mastered")]
        public bool? Mastered { get; set; }
    }
}