using UnityEngine;

namespace StickBalancing
{
    public sealed class CartChain
    {
        public ArticulationBody Cart { get; private set; }
        public ArticulationBody[] Links { get; private set; }
        readonly TaskContract config;

        public CartChain(Transform parent, TaskContract config)
        {
            this.config = config;
            config.Validate();
            var rail = new GameObject("Fixed rail anchor");
            rail.transform.SetParent(parent, false);
            rail.transform.localPosition = new Vector3(0, config.segments * config.segment_length + 1, 0);
            var root = rail.AddComponent<ArticulationBody>();
            root.immovable = true;
            root.useGravity = false;

            Cart = Body("Cart", rail.transform, Vector3.zero, config.cart_mass);
            Cart.jointType = ArticulationJointType.PrismaticJoint;
            Cart.anchorPosition = Vector3.zero;
            Cart.parentAnchorPosition = Vector3.zero;
            Cart.anchorRotation = Cart.parentAnchorRotation = Quaternion.identity;
            Cart.linearLockX = ArticulationDofLock.FreeMotion;
            Cart.linearLockY = Cart.linearLockZ = ArticulationDofLock.LockedMotion;
            Cart.inertiaTensor = new Vector3(.01f, .01f, .01f);
            Visual(Cart.transform, new Vector3(.4f, .2f, .3f), new Color(.95f, .65f, .15f));

            Links = new ArticulationBody[config.segments];
            Transform previous = Cart.transform;
            for (int i = 0; i < Links.Length; i++)
            {
                float parentOffset = i == 0 ? .1f : config.segment_length / 2;
                var link = Body($"Segment {i + 1}", previous,
                    new Vector3(0, parentOffset + config.segment_length / 2, 0), config.segment_mass);
                link.jointType = ArticulationJointType.RevoluteJoint;
                link.anchorPosition = new Vector3(0, -config.segment_length / 2, 0);
                link.parentAnchorPosition = new Vector3(0, parentOffset, 0);
                // Articulation revolute axis is anchor-local X; map it to world Z.
                link.anchorRotation = link.parentAnchorRotation = Quaternion.Euler(0, -90, 0);
                link.twistLock = ArticulationDofLock.FreeMotion;
                link.swingYLock = link.swingZLock = ArticulationDofLock.LockedMotion;
                float transverse = config.segment_mass * (config.segment_length * config.segment_length + .0036f) / 12;
                link.inertiaTensor = new Vector3(transverse, config.segment_mass * .0036f / 6, transverse);
                Visual(link.transform, new Vector3(.06f, config.segment_length, .06f), new Color(.15f, .8f, .9f));
                Links[i] = link;
                previous = link.transform;
            }
        }

        static ArticulationBody Body(string name, Transform parent, Vector3 localPosition, float mass)
        {
            var go = new GameObject(name);
            go.transform.SetParent(parent, false);
            go.transform.localPosition = localPosition;
            var body = go.AddComponent<ArticulationBody>();
            body.mass = mass;
            body.matchAnchors = false;
            body.centerOfMass = Vector3.zero;
            body.linearDamping = body.angularDamping = body.jointFriction = 0;
            body.solverIterations = 20;
            body.solverVelocityIterations = 10;
            body.xDrive = body.yDrive = body.zDrive = new ArticulationDrive {
                stiffness = 0, damping = 0, forceLimit = 0
            };
            return body;
        }

        static void Visual(Transform parent, Vector3 scale, Color color)
        {
            var visual = GameObject.CreatePrimitive(PrimitiveType.Cube);
            visual.transform.SetParent(parent, false);
            visual.transform.localScale = scale;
            // Explicit collision-free phase-0 experiment, including inter-link contacts.
            visual.GetComponent<Collider>().enabled = false;
            var material = Resources.Load<Material>("StickSurface");
            if (material != null) visual.GetComponent<Renderer>().sharedMaterial = material;
            var properties = new MaterialPropertyBlock();
            properties.SetColor("_Color", color);
            properties.SetColor("_BaseColor", color);
            visual.GetComponent<Renderer>().SetPropertyBlock(properties);
        }

        // Called only on episode resets. There are no position corrections during a trial.
        public void ResetDown(System.Random random, bool exact = false)
        {
            Cart.jointPosition = new ArticulationReducedSpace(0);
            Cart.jointVelocity = new ArticulationReducedSpace(0);
            Cart.jointForce = new ArticulationReducedSpace(0);
            for (int i = 0; i < Links.Length; i++)
            {
                float perturbation = exact ? 0 : (float)(random.NextDouble() * 2 - 1) * .02f;
                Links[i].jointPosition = new ArticulationReducedSpace((i == 0 ? Mathf.PI : 0) + perturbation);
                Links[i].jointVelocity = new ArticulationReducedSpace(0);
                Links[i].jointForce = new ArticulationReducedSpace(0);
            }
        }

        public void Read(float[] angles, float[] speeds)
        {
            for (int i = 0; i < Links.Length; i++)
            {
                angles[i] = Links[i].jointPosition[0];
                speeds[i] = Links[i].jointVelocity[0];
            }
        }

        public void Apply(float action) => Cart.AddForce(Vector3.right * Mathf.Clamp(action, -1, 1) * config.force_limit, ForceMode.Force);
    }
}
