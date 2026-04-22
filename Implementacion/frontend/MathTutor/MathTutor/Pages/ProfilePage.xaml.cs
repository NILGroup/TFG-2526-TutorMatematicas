using MathTutor.Models;
using MathTutor.PageModels;

namespace MathTutor.Pages
{
    public partial class ProfilePage : ContentPage
    {
        public ProfilePage(ProfilePageModel model)
        {
            InitializeComponent();
            BindingContext = model;
        }
    }
}