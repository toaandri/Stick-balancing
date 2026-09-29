using UnityEngine;

namespace StickBalancing
{
    public sealed class PendulumPreview : MonoBehaviour
    {
        public CartChain Chain { get; private set; }
        public TaskContract Configuration { get; private set; }
        GameObject assembly;

        void Start() { if (Chain == null) Configure(new TaskContract()); }

        public void ResetPreview() => Chain?.ResetDown(new System.Random(Configuration.seed));

        public void Configure(TaskContract task)
        {
            task.Validate();
            if (assembly != null) { assembly.SetActive(false); Destroy(assembly); }
            Configuration = task;
            assembly = new GameObject("Preview assembly");
            assembly.transform.SetParent(transform, false);
            Chain = new CartChain(assembly.transform, task);
            ResetPreview();
            var rail = GameObject.CreatePrimitive(PrimitiveType.Cube);
            rail.name = "Rail visual";
            rail.transform.SetParent(assembly.transform, false);
            rail.transform.localPosition = new Vector3(0, task.segments * task.segment_length + .84f, .2f);
            rail.transform.localScale = new Vector3(task.rail_half_length * 2, .08f, .08f);
            rail.GetComponent<Collider>().enabled = false;
            rail.GetComponent<Renderer>().sharedMaterial = Resources.Load<Material>("StickSurface");
        }
    }
}
