using MathTutor.Models;
using MathTutor.PageModels;

namespace MathTutor.Pages
{
    public partial class SettingsPage : ContentPage
    {
        public SettingsPage(SettingsPageModel model)
        {
            InitializeComponent();
            BindingContext = model;
        }
    }
}
