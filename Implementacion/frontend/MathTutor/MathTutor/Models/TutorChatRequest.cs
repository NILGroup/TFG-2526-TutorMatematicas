namespace MathTutor.Models
{
    public class TutorChatRequest
    {
        public string ProblemId { get; set; }
        public string Question { get; set; }
        public string? UserId { get; set; }
        public string? CurrentAttempt { get; set; }
    }
}
