using MathTutor.Models;
using MathTutor.PageModels;

namespace MathTutor.Pages
{
    public partial class ProblemsLibraryPage : ContentPage
    {
        private readonly ProblemsLibraryPageModel _model;

        public ProblemsLibraryPage(ProblemsLibraryPageModel model)
        {
            InitializeComponent();
            BindingContext = model;
            _model = model;
        }

        protected override async void OnAppearing()
        {
            base.OnAppearing();
            await _model.AppearingCommand.ExecuteAsync(null);
        }

        private async void OnProblemSelected(object sender, SelectionChangedEventArgs e)
        {
            if (e.CurrentSelection.FirstOrDefault() is not ProblemOut problem)
                return;

            // Clear selection immediately so we can re-select the same item later
            ProblemsCollectionView.SelectedItem = null;

            // Delegate the actual navigation to the page model command
            if (_model.OpenProblemCommand.CanExecute(problem.Id))
                await _model.OpenProblemCommand.ExecuteAsync(problem.Id);
        }
    }
}