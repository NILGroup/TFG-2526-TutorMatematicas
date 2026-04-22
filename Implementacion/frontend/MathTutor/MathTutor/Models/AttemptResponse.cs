using System.Collections.Generic;

namespace MathTutor.Models
{
    public class AttemptResponse
    {
        public bool Ok { get; set; }
        public Dictionary<string, float> UpdatedMastery { get; set; } = new();
    }
}
