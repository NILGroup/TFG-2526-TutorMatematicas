using System.Collections.Generic;

namespace MathTutor.Models
{
    public class StartSessionResponse
    {
        public string SessionId { get; set; }
        public List<string> ProblemIds { get; set; }
    }
}
