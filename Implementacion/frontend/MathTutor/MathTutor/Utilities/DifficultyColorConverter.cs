using System.Globalization;

namespace MathTutor.Utilities
{
    /// <summary>
    /// Maps a difficulty int (1–5) to a semantic color:
    /// 1 green → 2 lime → 3 amber → 4 orange → 5 red
    /// </summary>
    public class DifficultyColorConverter : IValueConverter
    {
        public object Convert(object? value, Type targetType, object? parameter, CultureInfo culture)
        {
            return (int?)value switch
            {
                1 => Color.FromArgb("#22C55E"),
                2 => Color.FromArgb("#84CC16"),
                3 => Color.FromArgb("#EAB308"),
                4 => Color.FromArgb("#F97316"),
                5 => Color.FromArgb("#EF4444"),
                _ => Color.FromArgb("#6B7280"),
            };
        }

        public object ConvertBack(object? value, Type targetType, object? parameter, CultureInfo culture)
            => throw new NotImplementedException();
    }
}
