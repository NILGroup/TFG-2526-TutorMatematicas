using System.Collections.Generic;

namespace MathTutor.Models
{
    public class ProblemOut
    {
        public string Id { get; set; }
        public string? Course { get; set; }
        public string? Kc { get; set; }
        public List<string> Tags { get; set; } = new();
        public int? Difficulty { get; set; }
        public string Statement { get; set; }
        public Dictionary<string, object> Parameters { get; set; } = new();
        public Dictionary<string, int> InstantiatedParameters { get; set; } = new();
    }
}
