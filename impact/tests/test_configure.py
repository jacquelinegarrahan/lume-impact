
def test_mpi_switch(impact_obj):
    """Tests MPI setter
    
    """

    assert impact_obj.use_mpi==False

    impact_obj.use_mpi = True
    # test switch True
    assert impact_obj.use_mpi==True


    impact_obj.use_mpi = False

    assert impact_obj.use_mpi==False