using System.Collections.Generic;

namespace MathTutor.Models
{
    public class TutorChatResponse
    {
        public string Answer { get; set; }
        public Dictionary<string, object> Meta { get; set; }
    }
}
