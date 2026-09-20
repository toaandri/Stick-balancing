using System;
using NUnit.Framework;

namespace StickBalancing.Tests
{
    public class SuccessMonitorTests
    {
        [Test]
        public void FullRotationIsUprightButNeedsConsecutiveHold()
        {
            var cfg = new TaskContract { physics_dt = .01f, hold_seconds = .1f };
            var monitor = new SuccessMonitor(cfg);
            for (int i = 0; i < 9; i++)
                Assert.AreEqual(EpisodeOutcome.Running, monitor.Step(0, new[] { (float)(2 * Math.PI) }, new[] { 0f }));
            Assert.AreEqual(EpisodeOutcome.Success, monitor.Step(0, new[] { 0f }, new[] { 0f }));
        }

        [Test]
        public void PassingTopAtSpeedResetsHold()
        {
            var cfg = new TaskContract { physics_dt = .01f, hold_seconds = .1f };
            var monitor = new SuccessMonitor(cfg);
            monitor.Step(0, new[] { 0f }, new[] { 0f });
            monitor.Step(0, new[] { 0f }, new[] { 2f });
            Assert.AreEqual(0, monitor.Held);
        }

        [Test]
        public void OppositeRelativeAnglesDoNotHideTiltedSegment()
        {
            var monitor = new SuccessMonitor(new TaskContract { segments = 2 });
            monitor.Step(0, new[] { .5f, -.5f }, new[] { 0f, 0f });
            Assert.AreEqual(0, monitor.Held);
        }

        [Test]
        public void RailExitWinsOverUprightPose()
        {
            var monitor = new SuccessMonitor(new TaskContract());
            Assert.AreEqual(EpisodeOutcome.RailExit, monitor.Step(2.5f, new[] { 0f }, new[] { 0f }));
        }
    }
}
