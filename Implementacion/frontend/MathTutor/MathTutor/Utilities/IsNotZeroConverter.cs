using System.Globalization;

namespace MathTutor.Utilities
{
    /// <summary>
    /// Converts an integer to a bool: true when value > 0, false otherwise.
    /// Used to toggle UI visibility based on collection counts without
    /// pulling in a heavier MVVM trigger.
    /// </summary>
    public class IsNotZeroConverter : IValueConverter
    {
        public object Convert(object? value, Type targetType, object? parameter, CultureInfo culture)
        {
            if (value is int i) return i > 0;
            if (value is long l) return l > 0;
            if (value is double d) return d > 0;
            return false;
        }

        public object ConvertBack(object? value, Type targetType, object? parameter, CultureInfo culture)
            => throw new NotImplementedException();
    }
}
