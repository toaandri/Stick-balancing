using UnityEngine;

namespace StickBalancing
{
    public sealed class PendulumPreview : MonoBehaviour
    {
        void Start()
        {
            var task = new TaskContract();
            var chain = new CartChain(transform, task);
            chain.ResetDown(new System.Random(task.seed), true);
            var rail = GameObject.CreatePrimitive(PrimitiveType.Cube);
            rail.name = "Rail visual";
            rail.transform.SetParent(transform, false);
            rail.transform.localPosition = new Vector3(0, 1.84f, .2f);
            rail.transform.localScale = new Vector3(5.2f, .08f, .08f);
            rail.GetComponent<Collider>().enabled = false;
            rail.GetComponent<Renderer>().sharedMaterial = Resources.Load<Material>("StickSurface");
        }
    }
}
