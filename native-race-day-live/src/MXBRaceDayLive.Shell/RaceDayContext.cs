using MXBRaceDayLive.Contracts;

namespace MXBRaceDayLive.Shell;

public sealed class RaceDayContext : IRaceDayContext
{
    public RaceDayContext(IMXBikesService mxbikes, IProfileStore profile, IUpdateService updates)
    {
        MXBikes = mxbikes;
        Profile = profile;
        Updates = updates;
    }

    public IMXBikesService MXBikes { get; }
    public IProfileStore Profile { get; }
    public IUpdateService Updates { get; }
}
