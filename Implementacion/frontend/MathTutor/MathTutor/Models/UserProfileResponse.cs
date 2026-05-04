using System.Collections.Generic;
using System.Text.Json.Serialization;

namespace MathTutor.Models
{
    public class UserProfileResponse
    {
        [JsonPropertyName("user_id")]
        public string UserId { get; set; } = string.Empty;

        [JsonPropertyName("name")]
        public string? Name { get; set; }

        [JsonPropertyName("profile")]
        public UserProfileInfo Profile { get; set; } = new();

        [JsonPropertyName("interests")]
        public UserInterestsInfo Interests { get; set; } = new();

        [JsonPropertyName("progress")]
        public UserProgressInfo Progress { get; set; } = new();
    }

    public class UserProfileInfo
    {
        [JsonPropertyName("course_level")]
        public string CourseLevel { get; set; } = "1º ESO";

        [JsonPropertyName("modality")]
        public string? Modality { get; set; }

        [JsonPropertyName("allow_cross_course")]
        public bool AllowCrossCourse { get; set; }
    }

    public class UserInterestsInfo
    {
        [JsonPropertyName("primary_objective")]
        public string PrimaryObjective { get; set; } = "PRACTICE";

        [JsonPropertyName("kc_scores")]
        public Dictionary<string, float> KcScores { get; set; } = new();

        [JsonPropertyName("tag_scores")]
        public Dictionary<string, Dictionary<string, float>> TagScores { get; set; } = new();

        [JsonPropertyName("difficulty_preferences")]
        public DifficultyPreferences DifficultyPreferences { get; set; } = new();

        [JsonPropertyName("session_preferences")]
        public SessionPreferences SessionPreferences { get; set; } = new();

        [JsonPropertyName("problem_preferences")]
        public ProblemPreferences ProblemPreferences { get; set; } = new();
    }

    public class UserProgressInfo
    {
        [JsonPropertyName("completed_problems")]
        public int CompletedProblems { get; set; }

        [JsonPropertyName("correct_attempts")]
        public int CorrectAttempts { get; set; }

        [JsonPropertyName("total_attempts")]
        public int TotalAttempts { get; set; }

        [JsonPropertyName("streak")]
        public int Streak { get; set; }
    }
}