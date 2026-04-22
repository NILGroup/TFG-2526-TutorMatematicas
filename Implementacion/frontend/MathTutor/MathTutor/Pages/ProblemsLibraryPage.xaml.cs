using MathTutor.Models;
using MathTutor.PageModels;

namespace MathTutor.Pages
{
    public partial class ProblemsLibraryPage : ContentPage
    {
        public ProblemsLibraryPage(ProblemsLibraryPageModel model)
        {
            InitializeComponent();
            BindingContext = model;
        }
    }
}