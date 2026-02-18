using CommunityToolkit.Mvvm.Input;
using MathTutor.Models;

namespace MathTutor.PageModels
{
    public interface IProjectTaskPageModel
    {
        IAsyncRelayCommand<ProjectTask> NavigateToTaskCommand { get; }
        bool IsBusy { get; }
    }
}