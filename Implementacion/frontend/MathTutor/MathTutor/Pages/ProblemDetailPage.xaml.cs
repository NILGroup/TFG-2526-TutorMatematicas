using MathTutor.PageModels;

namespace MathTutor.Pages
{
    public partial class ProblemDetailPage : ContentPage
    {
        private readonly ProblemDetailPageModel _model;

        public ProblemDetailPage(ProblemDetailPageModel model)
        {
            InitializeComponent();
            BindingContext = _model = model;

            // Scroll the chat list to the newest message whenever
            // the page model signals that one was added.
            //_model.ScrollToLastMessage += OnScrollToLastMessage;
        }
        /*
        private void OnScrollToLastMessage(object? sender, EventArgs e)
        {
            var messages = _model.ChatMessages;
            if (messages.Count == 0) return;

            // CollectionView.ScrollTo requires the item, not the index.
            ChatCollectionView.ScrollTo(
                item: messages[^1],
                animate: false,
                position: ScrollToPosition.End);
        }*/
    }
}
