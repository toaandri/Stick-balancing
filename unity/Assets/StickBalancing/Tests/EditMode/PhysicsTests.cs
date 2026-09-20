using System;
using NUnit.Framework;
using UnityEngine;

namespace StickBalancing.Tests
{
    // Real Unity physics, manually stepped. These must pass in the selected editor.
    public class PhysicsTests
    {
        GameObject root;
        CartChain chain;
        TaskContract config;
        SimulationMode previousMode;
        Vector3 previousGravity;

        [SetUp]
        public void Setup()
        {
            previousMode = Physics.simulationMode;
            previousGravity = Physics.gravity;
            Physics.simulationMode = SimulationMode.Script;
            Physics.gravity = new Vector3(0, -9.81f, 0);
            root = new GameObject("Physics test");
            config = new TaskContract();
            chain = new CartChain(root.transform, config);
            Physics.SyncTransforms();
            Physics.Simulate(config.physics_dt); // initialize reduced coordinates
            chain.ResetDown(new System.Random(42), true);
        }

        [TearDown]
        public void Cleanup()
        {
            UnityEngine.Object.DestroyImmediate(root);
            Physics.simulationMode = previousMode;
            Physics.gravity = previousGravity;
        }

        void Advance(int steps, float force = 0)
        {
            for (int i = 0; i < steps; i++)
            {
                chain.Apply(force);
                Physics.Simulate(config.physics_dt);
            }
        }

        [Test]
        public void DownRestRemainsDownAndFinite()
        {
            Advance(500);
            Assert.That(Math.Abs(chain.Cart.jointPosition[0]), Is.LessThan(.001));
            float angle = chain.Links[0].jointPosition[0];
            Assert.IsTrue(TaskContract.Finite(angle));
            Assert.That(Mathf.Cos(angle), Is.LessThan(-.999));
        }

        [TestCase(1f)]
        [TestCase(-1f)]
        public void CartRespondsToForceSign(float sign)
        {
            Advance(10, .1f * sign);
            Assert.That(chain.Cart.jointVelocity[0] * sign, Is.GreaterThan(0));
            Assert.That(Math.Abs(chain.Cart.transform.position.z), Is.LessThan(.0001));
        }

        [Test]
        public void PerturbedUprightFallsWithoutControl()
        {
            chain.Links[0].jointPosition = new ArticulationReducedSpace(.05f);
            Advance(400);
            Assert.That(Math.Abs(chain.Links[0].jointPosition[0]), Is.GreaterThan(.2));
        }

        [Test]
        public void HingesHaveNoActiveDrive()
        {
            foreach (var link in chain.Links)
            {
                Assert.AreEqual(0, link.xDrive.stiffness);
                Assert.AreEqual(0, link.xDrive.damping);
                Assert.AreEqual(0, link.xDrive.forceLimit);
                Assert.AreEqual(ArticulationJointType.RevoluteJoint, link.jointType);
            }
        }

        [Test]
        public void ActionSaturatesAndResetClearsMotion()
        {
            Advance(10, 1);
            float limited = chain.Cart.jointVelocity[0];
            chain.ResetDown(new System.Random(42), true);
            Advance(10, 100);
            Assert.That(chain.Cart.jointVelocity[0], Is.EqualTo(limited).Within(.001));
            chain.ResetDown(new System.Random(42), true);
            Assert.That(chain.Cart.jointPosition[0], Is.EqualTo(0).Within(.0001));
            Assert.That(chain.Cart.jointVelocity[0], Is.EqualTo(0).Within(.0001));
        }

        [Test]
        public void HalvingStepPreservesShortTrajectory()
        {
            Advance(100, .1f);
            float x = chain.Cart.jointPosition[0];
            float theta = chain.Links[0].jointPosition[0];
            chain.ResetDown(new System.Random(42), true);
            for (int i = 0; i < 200; i++)
            {
                chain.Apply(.1f);
                Physics.Simulate(config.physics_dt / 2);
            }
            Assert.That(chain.Cart.jointPosition[0], Is.EqualTo(x).Within(.01));
            Assert.That(chain.Links[0].jointPosition[0], Is.EqualTo(theta).Within(.01));
        }

        [Test]
        public void SmallDownOscillationsMatchFreeCartRodPeriod()
        {
            chain.Links[0].jointPosition = new ArticulationReducedSpace(Mathf.PI + .05f);
            float last = .05f;
            float firstCrossing = -1, secondCrossing = -1;
            for (int i = 1; i <= 2000; i++)
            {
                Advance(1);
                float current = Mathf.Atan2(Mathf.Sin(chain.Links[0].jointPosition[0] - Mathf.PI),
                                          Mathf.Cos(chain.Links[0].jointPosition[0] - Mathf.PI));
                if (last * current < 0)
                {
                    if (firstCrossing < 0) firstCrossing = i * config.physics_dt;
                    else { secondCrossing = i * config.physics_dt; break; }
                }
                last = current;
            }
            double m = config.segment_mass, M = config.cart_mass, L = config.segment_length;
            double effectiveInertia = m * L * L / 3 - m * m * L * L / (4 * (M + m));
            double expected = 2 * Math.PI * Math.Sqrt(effectiveInertia / (m * 9.81 * L / 2));
            Assert.That(secondCrossing, Is.GreaterThan(firstCrossing));
            Assert.That(2 * (secondCrossing - firstCrossing), Is.EqualTo(expected).Within(.03));
        }

        double Energy()
        {
            double m = config.segment_mass, M = config.cart_mass, L = config.segment_length;
            double xdot = chain.Cart.jointVelocity[0];
            double theta = chain.Links[0].jointPosition[0], omega = chain.Links[0].jointVelocity[0];
            // Positive Z rotation moves an initially upright centre of mass toward -X.
            return .5 * (M + m) * xdot * xdot - m * L / 2 * Math.Cos(theta) * xdot * omega
                + .5 * m * (L * L / 3 + .0036 / 12) * omega * omega
                + m * 9.81 * L / 2 * (1 + Math.Cos(theta));
        }

        [Test]
        public void UndampedUnforcedMotionDoesNotCreateEnergy()
        {
            chain.Links[0].jointPosition = new ArticulationReducedSpace(Mathf.PI + .4f);
            double initial = Energy();
            double maxRelativeError = 0;
            for (int i = 0; i < 2000; i++)
            {
                Advance(1);
                maxRelativeError = Math.Max(maxRelativeError, Math.Abs(Energy() - initial) / initial);
            }
            Assert.That(maxRelativeError, Is.LessThan(.03), "Energy drift exceeds 3% over 4 simulated seconds");
        }
    }
}
