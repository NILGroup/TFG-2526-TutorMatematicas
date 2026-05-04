using MathTutor.PageModels;

namespace MathTutor.Pages
{
    public partial class QuestionnairePage : ContentPage
    {
        public QuestionnairePage(QuestionnairePageModel model)
        {
            InitializeComponent();
            BindingContext = model;
        }
    }
}
