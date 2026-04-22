namespace MathTutor.Models
{
    public class StartSessionRequest
    {
        public string UserId { get; set; }
        public int K { get; set; } = 8;
        public string? Course { get; set; }
    }
}