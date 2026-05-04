using CommunityToolkit.Mvvm.ComponentModel;

namespace MathTutor.Models
{
    /// <summary>
    /// A single message in the tutor chat panel.
    /// Implements INotifyPropertyChanged via ObservableObject so that
    /// the typewriter effect (character-by-character Text updates) is
    /// reflected live in the CollectionView without replacing the item.
    /// </summary>
    public partial class ChatMessage : ObservableObject
    {
        // The text that is currently displayed. Updated incrementally
        // during the typewriter animation.
        [ObservableProperty]
        private string text = string.Empty;

        // True  → student bubble (right-aligned, primary colour)
        // False → tutor bubble  (left-aligned, card colour)
        public bool IsUser { get; init; }
    }
}
