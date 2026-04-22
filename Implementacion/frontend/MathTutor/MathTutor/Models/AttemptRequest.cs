namespace MathTutor.Models
{
    public class AttemptRequest
    {
        public string UserId { get; set; }
        public string ProblemId { get; set; }
        public bool IsCorrect { get; set; }
        public string? StudentAnswer { get; set; }
        public int? SecondsSpent { get; set; }
    }
}
