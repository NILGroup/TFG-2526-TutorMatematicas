using MathTutor.Models;
using MathTutor.PageModels;

namespace MathTutor.Pages
{
    public partial class MainPage : ContentPage
    {
        private readonly MainPageModel _model;

        public MainPage(MainPageModel model)
        {
            InitializeComponent();
            BindingContext = model;
            _model = model;
        }

        private async void OnProblemSelected(object sender, SelectionChangedEventArgs e)
        {
            if (e.CurrentSelection.FirstOrDefault() is not ProblemOut problem)
                return;

            ProblemsCollectionView.SelectedItem = null;

            if (_model.StartProblemCommand.CanExecute(problem.Id))
                await _model.StartProblemCommand.ExecuteAsync(problem.Id);
        }
    }
}