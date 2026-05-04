using System.Collections.Generic;
using System.Text.Json.Serialization;

namespace MathTutor.Models
{
    public class UserInterestsRequest
    {
        [JsonPropertyName("user_id")]
        public string UserId { get; set; } = "user123";

        [JsonPropertyName("course_level")]
        public string CourseLevel { get; set; } = "3ESO";

        [JsonPropertyName("modality")]
        public string? Modality { get; set; }

        [JsonPropertyName("allow_cross_course")]
        public bool AllowCrossCourse { get; set; }

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

    public class DifficultyPreferences
    {
        [JsonPropertyName("min_difficulty")]
        public int MinDifficulty { get; set; } = 1;

        [JsonPropertyName("max_difficulty")]
        public int MaxDifficulty { get; set; } = 3;

        [JsonPropertyName("target_difficulty")]
        public int TargetDifficulty { get; set; } = 2;

        [JsonPropertyName("trend")]
        public string Trend { get; set; } = "STABLE";
    }

    public class SessionPreferences
    {
        [JsonPropertyName("problems_per_session")]
        public int ProblemsPerSession { get; set; } = 5;

        [JsonPropertyName("sessions_per_week")]
        public int SessionsPerWeek { get; set; } = 4;
    }

    public class ProblemPreferences
    {
        [JsonPropertyName("repetition_preference")]
        public string RepetitionPreference { get; set; } = "MEDIUM";

        [JsonPropertyName("statement_length_preference")]
        public string StatementLengthPreference { get; set; } = "MEDIUM";

        [JsonPropertyName("multi_topic_preference")]
        public string MultiTopicPreference { get; set; } = "NO_PREFERENCE";
    }
}